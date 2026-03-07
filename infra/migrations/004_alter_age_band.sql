-- Increase size of age band columns

ALTER TABLE documents ALTER COLUMN age_band TYPE character varying(20);
ALTER TABLE recommendations ALTER COLUMN age_band TYPE character varying(20);

