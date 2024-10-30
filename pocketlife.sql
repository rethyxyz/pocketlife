CREATE DATABASE IF NOT EXISTS project_db; USE project_db;

CREATE TABLE IF NOT EXISTS arguments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    arguments TEXT
);

CREATE TABLE IF NOT EXISTS bandwidth (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_kb DOUBLE,
    received_kb DOUBLE
);

CREATE TABLE IF NOT EXISTS device_info (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    language VARCHAR(50),
    operating_system TEXT,
    public_ip_address VARCHAR(45)
);

CREATE TABLE IF NOT EXISTS function_trace (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    result TEXT,
    function_name VARCHAR(100),
    execution_time DOUBLE,
    cpu_usage_change DOUBLE,
    ram_usage_change DOUBLE,
    function_arguments TEXT
);
