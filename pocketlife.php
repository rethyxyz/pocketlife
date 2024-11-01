<?php

/*
 * https://rethy.xyz/Software/pocketlife
 * Updated documentation can be found here.
 */

/* API header name. */
$api_name = "Telemetry API";

/* Database connection variables. */
$servername = "localhost";
$username = "db_user";
$password = "db_pass";
$dbname = "pocketlife";

/* API credentials. */
define('API_USERNAME', 'api_username');
define('API_PASSWORD', 'api_password');

/* Create connection */
try {
    $conn = new mysqli($servername, $username, $password, $dbname);
}
catch (Exception $e)
{
    die("Error connecting to \"$dbname\" database.");
    //die("Error connecting to \"$dbname\" database: <br><br>$e.");
}

/* Check connection. */
if ($conn->connect_error)
{
    http_response_code(500); // Internal Server Error
    die("Connection failed: " . $conn->connect_error);
}

header('Content-Type: application/json');

if (!isset($_SERVER['PHP_AUTH_USER']))
{
    header('WWW-Authenticate: Basic realm="'.$api_name.'"');
    http_response_code(401); // Unauthorized
    echo json_encode(["error" => "Authentication required."]);
    exit();
}
else
{
    $provided_username = $_SERVER['PHP_AUTH_USER'];
    $provided_password = $_SERVER['PHP_AUTH_PW'];

    // Validate credentials
    if ($provided_username !== API_USERNAME || $provided_password !== API_PASSWORD)
    {
        header('WWW-Authenticate: Basic realm="'.$api_name.'"');
        http_response_code(401); // Unauthorized
        echo json_encode(["error" => "Invalid credentials."]);
        exit();
    }
}

/* Get the raw data. */
$json = file_get_contents('php://input');

/* Decode the data (assuming it's JSON). */
$data = json_decode($json, true);

if ($data === null && json_last_error() !== JSON_ERROR_NONE)
{
    http_response_code(400); // Bad Request
    echo json_encode(["error" => "Invalid JSON data: " . json_last_error_msg()]);
    exit();
}

// Initialize response array
$response = [];

// Process the data based on its content
try
{
    // Process 'arguments' data
    if (isset($data['arguments']))
    {
        $arguments = $data['arguments'];

        $stmt = $conn->prepare("INSERT INTO arguments (arguments) VALUES (?)");
        $stmt->bind_param("s", $arguments);
        $stmt->execute();
        $stmt->close();

        $response['status'] = "success";
        $response['message'] = "Arguments data inserted successfully.";

    // Process 'bandwidth' data
    }
    elseif (isset($data['bandwidth']))
    {
        // Extract sent_kb and received_kb using regex
        if (preg_match('/sent_kb: ([\d\.]+) received_kb: ([\d\.]+)/', $data['bandwidth'], $matches))
        {
            $sent_kb = floatval($matches[1]);
            $received_kb = floatval($matches[2]);

            $stmt = $conn->prepare("INSERT INTO bandwidth (sent_kb, received_kb) VALUES (?, ?)");
            $stmt->bind_param("dd", $sent_kb, $received_kb);
            $stmt->execute();
            $stmt->close();

            $response['status'] = "success";
            $response['message'] = "Bandwidth data inserted successfully.";
        }
        else
        {
            http_response_code(400); // Bad Request
            $response['error'] = "Failed to parse bandwidth data.";
        }

    // Process 'device_info' data
    }
    elseif (isset($data['Language']) || isset($data['OperatingSystem']) || isset($data['PublicIPAddress']))
    {
        $language = $data['Language'] ?? '';
        $operating_system = $data['OperatingSystem'] ?? '';
        $public_ip_address = $data['PublicIPAddress'] ?? '';

        $stmt = $conn->prepare("INSERT INTO device_info (language, operating_system, public_ip_address) VALUES (?, ?, ?)");
        $stmt->bind_param("sss", $language, $operating_system, $public_ip_address);
        $stmt->execute();
        $stmt->close();

        $response['status'] = "success";
        $response['message'] = "Device information inserted successfully.";

    // Process 'function_trace' data
    }
    elseif (isset($data['function_name']))
    {
        $result = isset($data['result']) ? json_encode($data['result']) : null;
        $function_name = $data['function_name'];
        $execution_time = isset($data['execution_time']) ? floatval($data['execution_time']) : null;
        $cpu_usage_change = isset($data['cpu_usage_change']) ? floatval($data['cpu_usage_change']) : null;
        $ram_usage_change = isset($data['ram_usage_change']) ? floatval($data['ram_usage_change']) : null;
        $function_arguments = isset($data['function_arguments']) ? $data['function_arguments'] : null;

        $stmt = $conn->prepare("INSERT INTO function_trace (result, function_name, execution_time, cpu_usage_change, ram_usage_change, function_arguments) VALUES (?, ?, ?, ?, ?, ?)");
        $stmt->bind_param("ssddds", $result, $function_name, $execution_time, $cpu_usage_change, $ram_usage_change, $function_arguments);
        $stmt->execute();
        $stmt->close();

        $response['status'] = "success";
        $response['message'] = "Function trace data inserted successfully.";

    // Process 'program_usage' data
    }
    elseif (isset($data['CPUUsage']) || isset($data['RAMUsage']))
    {
        $cpu_usage = isset($data['CPUUsage']) ? floatval($data['CPUUsage']) : null;
        $ram_usage = isset($data['RAMUsage']) ? floatval($data['RAMUsage']) : null;

        $stmt = $conn->prepare("INSERT INTO program_usage (cpu_usage, ram_usage) VALUES (?, ?)");
        $stmt->bind_param("dd", $cpu_usage, $ram_usage);
        $stmt->execute();
        $stmt->close();

        $response['status'] = "success";
        $response['message'] = "Program usage data inserted successfully.";

    }
    else
    {
        http_response_code(400); // Bad Request
        $response['error'] = "Unrecognized data format.";
    }
} catch (Exception $e) {
    http_response_code(500); // Internal Server Error
    $response['error'] = "An error occurred: " . $e->getMessage();
}

// Close the database connection
$conn->close();

// Return the response as JSON
echo json_encode($response);
