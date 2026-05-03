-- Создаётся postgres'ом из /docker-entrypoint-initdb.d/.
-- Создаёт пользователей и БД для krisha_dwh и airflow.

-- Krisha DWH
CREATE USER krisha WITH PASSWORD 'krisha_secret_2026';
CREATE DATABASE krisha_dwh OWNER krisha;
GRANT ALL PRIVILEGES ON DATABASE krisha_dwh TO krisha;

-- Airflow metadata
CREATE USER airflow WITH PASSWORD 'airflow_secret_2026';
CREATE DATABASE airflow_db OWNER airflow;
GRANT ALL PRIVILEGES ON DATABASE airflow_db TO airflow;

-- Расширения в krisha_dwh
\connect krisha_dwh
CREATE EXTENSION IF NOT EXISTS pgcrypto;
GRANT ALL ON SCHEMA public TO krisha;
