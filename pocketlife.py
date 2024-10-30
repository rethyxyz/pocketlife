import os
import json
import time
import psutil
import locale
import platform
import urllib.request
import requests
import sys
from functools import wraps
import sys
import base64

DEBUG = "ON"

class Fetch:
    '''Pulls telemetry information from device, network, and resources.'''

    def Arguments():
        return str(sys.argv)

    def Language():
        try:
            lang, _ = locale.getdefaultlocale()
            return lang or ""
        except Exception:
            return ""

    def OperatingSystem():
        os_name = platform.system()
        os_version = platform.version()
        return f"{os_name} {os_version}"

    def PublicIPAddress():
        '''Get public IP address from an online API. Ideally, use the pocketlife
        telemetry server as a way to receive the public IP address (TODO).'''
        try:
            with urllib.request.urlopen("https://api.ipify.org?format=json", timeout=5) as response:
                data = json.load(response)
                return data.get("ip", "")
        except Exception:
            return ""

    def CPUUsage():
        ''' Gets the current CPU usage of the Python program at the exact moment
        this function is called.  '''
        try:
            # Get the current process using its PID
            process = psutil.Process(os.getpid())

            # Get the CPU usage percentage (instantaneous)
            cpu_usage = process.cpu_percent(interval=0)

            return cpu_usage
        except Exception as e:
            return {"error": str(e)}

    def RAMUsage():
        ''' Gets the current RAM usage of the Python program at the exact moment
        this function is called.  Returns the usage in MB. '''
        try:
            # Get the current process using its PID
            process = psutil.Process(os.getpid())
            
            # Get the memory usage in bytes and convert to MB
            ram_usage_mb = process.memory_info().rss / (1024 ** 2)
            
            return ram_usage_mb
        except Exception as e:
            return {"error": str(e)}

    def Bandwidth():
        ''' Gets the current system-wide network bandwidth usage at the moment
        this function is called. Returns the total bytes sent and received since
        the system started.
        '''
        try:
            net_io = psutil.net_io_counters()

            # Capture the bytes sent and received
            sent_kb = net_io.bytes_sent / 1024
            recv_kb = net_io.bytes_recv / 1024

            return f"sent_kb: {sent_kb} received_kb: {recv_kb}"
        except Exception as e:
            return f"error: {str(e)}"


class User:
    ''' User Telemetry '''

    def Device():
        '''Upload device metrics, like operating system, IP address,
        geolocation, system language, etc.'''
        Language = Fetch.Language()
        OperatingSystem = Fetch.OperatingSystem()
        PublicIPAddress = Fetch.PublicIPAddress()

        Global.Post("device", [Language, OperatingSystem, PublicIPAddress])


class Network:
    '''Network Telemetry'''

    def Bandwidth():
        '''Overall bandwidth'''
        bandwidth = Fetch.Bandwidth()
        Global.Post("bandwidth", [bandwidth])


class Application:
    '''Application Telemetry'''

    def Arguments():
        ''' POST list of intial arguments defined upon inital run, or at any
        point. '''
        arguments = Fetch.Arguments()
        Global.Post("arguments", [arguments])

    def FunctionTrace(func):
        '''Decorator to trace RAM usage, CPU usage, execution time, and function arguments of a function.'''
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get the current process to monitor resource usage
            process = psutil.Process(os.getpid())
            
            # Record the start time and initial CPU/RAM usage
            start_time = time.time()
            start_cpu = process.cpu_percent(interval=None)
            start_ram = process.memory_info().rss

            # Capture function arguments
            try:
                # Attempt to serialize the arguments to JSON
                function_arguments = json.dumps({
                    'args': args,
                    'kwargs': kwargs
                }, default=str)
            except Exception as e:
                # Fallback to string representation if serialization fails
                function_arguments = str({'args': args, 'kwargs': kwargs})
            
            # Execute the function
            result = func(*args, **kwargs)
            
            # Record the end time and final CPU/RAM usage
            end_time = time.time()
            end_cpu = process.cpu_percent(interval=None)
            end_ram = process.memory_info().rss
            
            # Calculate the metrics
            elapsed_time = end_time - start_time
            cpu_usage = end_cpu - start_cpu
            ram_usage_mb = (end_ram - start_ram) / (1024 ** 2)

            function_name = func.__name__
            execution_time = f"{elapsed_time:.4f}"
            cpu_usage_change = f"{cpu_usage:.2f}"
            ram_usage_change = f"{ram_usage_mb:.2f}"

            # Include function_arguments in the data sent to Post
            Global.Post("function_trace", [
                result,
                function_name,
                execution_time,
                cpu_usage_change,
                ram_usage_change,
                function_arguments
            ])

            return result  # Return the result of the function

        return wrapper

class Global:
    '''Configurator and less specific functions lie here.'''

    def Post(category, data_list):
        '''
        Sorts data and uploads POST data to the destination telemetry server.

        Processes the following:
            function_trace
            arguments
            bandwidth
            device
        '''
        #check_configuration()  # Ensure that configure() has been called

        # Assemble the data based on the category
        if category == "function_trace":
            result = data_list[0]
            function_name = data_list[1]
            execution_time = data_list[2]
            cpu_usage_change = data_list[3]
            ram_usage_change = data_list[4]
            function_arguments = data_list[5]

            # Handle serialization of the result
            if isinstance(result, bytes):
                # Convert bytes to base64 encoded string
                result_serialized = base64.b64encode(result).decode('ascii')
            else:
                # Try to serialize result, or convert to string
                try:
                    json.dumps(result)  # Test if result is serializable
                    result_serialized = result
                except TypeError:
                    result_serialized = str(result)

            # Assemble the data into a dictionary
            data = {
                "result": result_serialized,
                "function_name": function_name,
                "execution_time": execution_time,
                "cpu_usage_change": cpu_usage_change,
                "ram_usage_change": ram_usage_change,
                "function_arguments": function_arguments
            }
        elif category == "arguments":
            arguments = data_list[0]
            data = {"arguments": arguments}
        elif category == "bandwidth":
            bandwidth = data_list[0]
            data = {"bandwidth": bandwidth}
        elif category == "device":
            Language = data_list[0]
            OperatingSystem = data_list[1]
            PublicIPAddress = data_list[2]

            data = {
                "Language": Language,
                "OperatingSystem": OperatingSystem,
                "PublicIPAddress": PublicIPAddress
            }
        else:
            data = {}

        # Serialize the data, handling bytes objects
        def custom_default(o):
            if isinstance(o, bytes):
                return base64.b64encode(o).decode('ascii')
            else:
                return str(o)

        json_data = json.dumps(data, default=custom_default)
        Global.Debug(f"Prepared JSON data: {json_data}")

        # Send the POST request
        try:
            # Construct the URL
            url = f"{POCKETLIFE_HOSTNAME}/telemetry_api.php"  # Adjust the endpoint as needed

            # Set up the headers
            headers = {'Content-Type': 'application/json'}

            # Use Basic Authentication
            auth = (POCKETLIFE_USERNAME, POCKETLIFE_PASSWORD)

            # Send the POST request with authentication
            response = requests.post(url, data=json_data, headers=headers, auth=auth, timeout=10)

            # Check for HTTP errors
            response.raise_for_status()

            # Log the response from the server
            Global.Debug(f"Data posted to {url}. Server response: {response.status_code} - {response.text}")

        except requests.exceptions.HTTPError as http_err:
            Global.Debug(f"HTTP error occurred: {http_err} - Response content: {response.text}")
        except requests.exceptions.ConnectionError as conn_err:
            Global.Debug(f"Connection error occurred: {conn_err}")
        except requests.exceptions.Timeout as timeout_err:
            Global.Debug(f"Timeout error occurred: {timeout_err}")
        except Exception as e:
            Global.Debug(f"An error occurred: {e}")


    def Configure(username, password, hostname):
        '''Assigns username/password/hostname to global variables. Mandatory function.'''
        global POCKETLIFE_USERNAME, POCKETLIFE_PASSWORD, POCKETLIFE_HOSTNAME
        POCKETLIFE_USERNAME = username
        POCKETLIFE_PASSWORD = password
        POCKETLIFE_HOSTNAME = hostname
    def Debug(message):
        '''Enables print statement'''
        if DEBUG == "ON": print(str(message))
    def Name():
        print("pocketlife: telemetry system")