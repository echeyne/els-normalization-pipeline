"""Text extraction module using AWS Textract."""

import logging
from typing import List, Dict, Any
import boto3
from botocore.exceptions import ClientError

from .models import TextBlock, ExtractionResult
from .config import Config

logger = logging.getLogger(__name__)


def extract_text(s3_key: str, s3_version_id: str) -> ExtractionResult:
    """
    Extract text from a document stored in S3 using AWS Textract.
    
    Args:
        s3_key: S3 key of the document
        s3_version_id: S3 version ID of the document
        
    Returns:
        ExtractionResult containing extracted text blocks or error information
    """
    try:
        textract_client = boto3.client('textract', region_name=Config.AWS_REGION)
        
        # Synchronous AnalyzeDocument only supports single-page documents (images).
        # PDFs can be multi-page even when small, so always use async for them.
        is_pdf = s3_key.lower().endswith('.pdf')
        if is_pdf:
            textract_response = _extract_async(textract_client, s3_key, s3_version_id)
        else:
            # Images (JPEG, PNG, TIFF) are single-page, safe for sync
            textract_response = _extract_sync(textract_client, s3_key, s3_version_id)
        
        if not textract_response:
            logger.error(f"Textract extraction failed for {s3_key}")
            return ExtractionResult(
                document_s3_key=s3_key,
                blocks=[],
                total_pages=1,
                status="error",
                error="Textract extraction failed"
            )
        
        # Parse Textract response into TextBlock objects
        blocks = _parse_textract_response(textract_response)
        
        if not blocks:
            logger.warning(f"Empty extraction output for {s3_key}")
            return ExtractionResult(
                document_s3_key=s3_key,
                blocks=[],
                total_pages=1,
                status="error",
                error="Empty extraction output"
            )
        
        # Sort blocks by reading order
        sorted_blocks = _sort_blocks_by_reading_order(blocks)
        
        # Determine total pages
        total_pages = max(block.page_number for block in sorted_blocks) if sorted_blocks else 1
        
        return ExtractionResult(
            document_s3_key=s3_key,
            blocks=sorted_blocks,
            total_pages=total_pages,
            status="success",
            error=None
        )
        
    except Exception as e:
        logger.error(f"Unexpected error during text extraction for {s3_key}: {e}", exc_info=True)
        return ExtractionResult(
            document_s3_key=s3_key,
            blocks=[],
            total_pages=1,
            status="error",
            error=f"Unexpected error: {str(e)}"
        )


def _extract_sync(textract_client, s3_key: str, s3_version_id: str) -> Dict[str, Any]:
    """
    Perform synchronous Textract extraction.
    
    Args:
        textract_client: Boto3 Textract client
        s3_key: S3 key of the document
        s3_version_id: S3 version ID
        
    Returns:
        Textract response dictionary
    """
    try:
        s3_object = {
            'Bucket': Config.S3_RAW_BUCKET,
            'Name': s3_key
        }
        if s3_version_id:
            s3_object['Version'] = s3_version_id
        
        response = textract_client.analyze_document(
            Document={'S3Object': s3_object},
            FeatureTypes=['TABLES']
        )
        return response
    except ClientError as e:
        logger.error(f"Textract sync extraction failed for {s3_key}: {e}")
        return None


def _extract_async(textract_client, s3_key: str, s3_version_id: str) -> Dict[str, Any]:
    """
    Perform asynchronous Textract extraction.
    
    This uses StartDocumentAnalysis and polls for completion.
    Required for multi-page documents.
    
    Args:
        textract_client: Boto3 Textract client
        s3_key: S3 key of the document
        s3_version_id: S3 version ID
        
    Returns:
        Textract response dictionary with all pages combined
    """
    import time
    
    try:
        s3_object = {
            'Bucket': Config.S3_RAW_BUCKET,
            'Name': s3_key
        }
        if s3_version_id:
            s3_object['Version'] = s3_version_id
        
        # Start async job
        logger.info(f"Starting async Textract job for {s3_key}")
        start_response = textract_client.start_document_analysis(
            DocumentLocation={'S3Object': s3_object},
            FeatureTypes=['TABLES']
        )
        
        job_id = start_response['JobId']
        logger.info(f"Textract job started with ID: {job_id}")
        
        # Poll for completion
        max_attempts = 60  # 5 minutes max (5 second intervals)
        attempt = 0
        
        while attempt < max_attempts:
            time.sleep(5)
            attempt += 1
            
            status_response = textract_client.get_document_analysis(JobId=job_id)
            status = status_response['JobStatus']
            
            logger.info(f"Textract job {job_id} status: {status} (attempt {attempt}/{max_attempts})")
            
            if status == 'SUCCEEDED':
                # Collect all pages
                all_blocks = status_response.get('Blocks', [])
                next_token = status_response.get('NextToken')
                
                # Paginate through results if needed
                while next_token:
                    logger.info(f"Fetching next page of results for job {job_id}")
                    next_response = textract_client.get_document_analysis(
                        JobId=job_id,
                        NextToken=next_token
                    )
                    all_blocks.extend(next_response.get('Blocks', []))
                    next_token = next_response.get('NextToken')
                
                logger.info(f"Textract job {job_id} completed successfully with {len(all_blocks)} blocks")
                return {'Blocks': all_blocks}
                
            elif status == 'FAILED':
                logger.error(f"Textract job {job_id} failed")
                return None
                
            elif status in ['IN_PROGRESS', 'PARTIAL_SUCCESS']:
                continue
            else:
                logger.error(f"Unexpected Textract job status: {status}")
                return None
        
        logger.error(f"Textract job {job_id} timed out after {max_attempts} attempts")
        return None
        
    except ClientError as e:
        logger.error(f"Textract async extraction failed for {s3_key}: {e}")
        return None


def _parse_textract_response(response: Dict[str, Any]) -> List[TextBlock]:
    """
    Parse Textract response into TextBlock objects.
    
    Args:
        response: Textract API response
        
    Returns:
        List of TextBlock objects
    """
    blocks = []
    
    for block in response.get('Blocks', []):
        block_type = block.get('BlockType', '')
        
        # We're interested in LINE and CELL blocks
        if block_type not in ['LINE', 'CELL']:
            continue
        
        text = block.get('Text', '')
        if not text:
            continue
        
        page_number = block.get('Page', 1)
        confidence = block.get('Confidence', 0.0) / 100.0  # Convert to 0-1 range
        geometry = block.get('Geometry', {})
        
        # Extract table cell information if present
        row_index = None
        col_index = None
        if block_type == 'CELL':
            row_index = block.get('RowIndex')
            col_index = block.get('ColumnIndex')
            # Textract uses 1-based indexing, convert to 0-based
            if row_index is not None:
                row_index = row_index - 1
            if col_index is not None:
                col_index = col_index - 1
        
        # Map CELL to TABLE_CELL for consistency with design
        mapped_block_type = 'TABLE_CELL' if block_type == 'CELL' else block_type
        
        text_block = TextBlock(
            text=text,
            page_number=page_number,
            block_type=mapped_block_type,
            row_index=row_index,
            col_index=col_index,
            confidence=confidence,
            geometry=geometry
        )
        
        blocks.append(text_block)
    
    return blocks


def _sort_blocks_by_reading_order(blocks: List[TextBlock]) -> List[TextBlock]:
    """
    Sort text blocks by reading order: (page_number, top_position, left_position).
    
    Args:
        blocks: List of TextBlock objects
        
    Returns:
        Sorted list of TextBlock objects
    """
    def get_sort_key(block: TextBlock) -> tuple:
        """Extract sort key from block geometry."""
        geometry = block.geometry
        bounding_box = geometry.get('BoundingBox', {})
        top = bounding_box.get('Top', 0.0)
        left = bounding_box.get('Left', 0.0)
        
        return (block.page_number, top, left)
    
    return sorted(blocks, key=get_sort_key)
