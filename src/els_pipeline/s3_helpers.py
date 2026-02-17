"""S3 helper functions for the ELS pipeline."""

import json
import logging
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

from .config import Config

logger = logging.getLogger(__name__)


def save_json_to_s3(data: dict, bucket: str, key: str) -> None:
    """
    Save JSON data to S3.

    Args:
        data: Dictionary to serialize and save
        bucket: S3 bucket name
        key: S3 object key

    Raises:
        ClientError: If S3 operation fails
    """
    try:
        s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
        json_data = json.dumps(data, indent=2)
        
        logger.info(f"Saving JSON to S3: bucket={bucket}, key={key}, size={len(json_data)} bytes")
        
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json_data,
            ContentType='application/json'
        )
        
        logger.info(f"Successfully saved JSON to S3: s3://{bucket}/{key}")
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        
        logger.error(
            f"Failed to save JSON to S3: bucket={bucket}, key={key}, "
            f"error_code={error_code}, error_msg={error_msg}"
        )
        
        if error_code == 'AccessDenied':
            raise ClientError(
                {
                    'Error': {
                        'Code': error_code,
                        'Message': f"Access denied when saving to S3. IAM permissions may need to be updated for bucket={bucket}, key={key}"
                    }
                },
                'PutObject'
            ) from e
        
        raise


def load_json_from_s3(bucket: str, key: str) -> Dict[str, Any]:
    """
    Load JSON data from S3.

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        Deserialized JSON as dictionary

    Raises:
        ClientError: If S3 operation fails
    """
    try:
        s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
        
        logger.info(f"Loading JSON from S3: bucket={bucket}, key={key}")
        
        response = s3_client.get_object(Bucket=bucket, Key=key)
        json_data = response['Body'].read()
        data = json.loads(json_data)
        
        logger.info(f"Successfully loaded JSON from S3: s3://{bucket}/{key}, size={len(json_data)} bytes")
        
        return data
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        
        logger.error(
            f"Failed to load JSON from S3: bucket={bucket}, key={key}, "
            f"error_code={error_code}, error_msg={error_msg}"
        )
        
        if error_code == 'NoSuchKey':
            raise ClientError(
                {
                    'Error': {
                        'Code': error_code,
                        'Message': f"Expected intermediate data was not found in S3: s3://{bucket}/{key}"
                    }
                },
                'GetObject'
            ) from e
        elif error_code == 'AccessDenied':
            raise ClientError(
                {
                    'Error': {
                        'Code': error_code,
                        'Message': f"Access denied when loading from S3. IAM permissions may need to be updated for bucket={bucket}, key={key}"
                    }
                },
                'GetObject'
            ) from e
        
        raise


def construct_intermediate_key(
    country: str,
    state: str,
    year: int,
    stage: str,
    run_id: str
) -> str:
    """
    Construct S3 key for intermediate data.

    Args:
        country: Country code
        state: State code
        year: Version year
        stage: Pipeline stage (extraction, detection, parsing, validation)
        run_id: Pipeline run ID

    Returns:
        S3 key following pattern: {country}/{state}/{year}/intermediate/{stage}/{run_id}.json
    """
    key = f"{country}/{state}/{year}/intermediate/{stage}/{run_id}.json"
    
    logger.debug(
        f"Constructed intermediate key: {key} "
        f"(country={country}, state={state}, year={year}, stage={stage}, run_id={run_id})"
    )
    
    return key
