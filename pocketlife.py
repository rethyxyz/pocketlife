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
import base64
from pathlib import Path

DEBUG = True
_last_cpu_times = None
_last_time = None

POCKETLIFE_QUEUE = Path.home() / ".pocketlife-queue.json"

class Fetch:
    '''Pulls telemetry information from the device, network, or resources.'''

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
        ''' Returns the current CPU % that the source program is using.  '''
        global _last_cpu_times, _last_time
        try:
            process = psutil.Process(os.getpid())

            current_cpu_times = process.cpu_times()
            current_time = time.time()

            if _last_cpu_times is None or _last_time is None:
                _last_cpu_times = current_cpu_times
                _last_time = current_time
                return 0.0

            cpu_time_delta = (
                (current_cpu_times.user - _last_cpu_times.user) +
                (current_cpu_times.system - _last_cpu_times.system)
            )

            time_delta = current_time - _last_time

            if time_delta == 0:
                cpu_usage = 0.0
            else:
                cpu_usage = (cpu_time_delta / time_delta) * 100

            _last_cpu_times = current_cpu_times
            _last_time = current_time

            return cpu_usage
        except Exception as e:
            return {"error": str(e)}

    def RAMUsage():
        ''' Gets the current RAM usage of the Python program at the exact moment
        this function is called.  Returns the usage in MB. '''
        try:
            process = psutil.Process(os.getpid())
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
    '''
    Network Telemetry

    Wrapper functions specifically about the inbound and outbound traffic of the
    source (calling) program or device.
    '''

    def Bandwidth():
        '''
        Bandwidth is derived from TODO.
        '''
        bandwidth = Fetch.Bandwidth()
        Global.Post("bandwidth", [bandwidth])

class Application:
    '''
    Application Telemetry

    Wrapper functions that fetch and post data related to source (calling)
    program runtime information.
    '''

    def ProgramUsage():
        CPUUsage = str(Fetch.CPUUsage())
        RAMUsage = str(Fetch.RAMUsage())+ " MB"
        #Global.Debug(str(CPUUsage) + " " + str(RAMUsage))
        Global.Post("program_usage", [CPUUsage, RAMUsage])

    def Arguments():
        '''
        Pull the argument list defined at a point in runtime, and POST it to
        the telemetry server.
        '''
        arguments = Fetch.Arguments()
        Global.Post("arguments", [arguments])

    def FunctionTrace(func):
        '''
        Decorator to trace RAM usage, CPU usage, execution time, and arguments
        of a function.
        '''
        @wraps(func)
        def wrapper(*args, **kwargs):
            process = psutil.Process(os.getpid())
            
            start_time = time.time()
            # TODO: Inaccurate, doesn't provide much information.
            start_cpu = process.cpu_percent(interval=None)
            # TODO: Inaccurate, doesn't provide much information.
            start_ram = process.memory_info().rss

            try:
                function_arguments = json.dumps({
                    'args': args,
                    'kwargs': kwargs
                }, default=str)
            except Exception as e:
                function_arguments = str({'args': args, 'kwargs': kwargs})
            
            result = func(*args, **kwargs)
            
            end_time = time.time()
            end_cpu = process.cpu_percent(interval=None)
            end_ram = process.memory_info().rss
            
            elapsed_time = end_time - start_time
            # TODO: Inaccurate, doesn't provide much information.
            cpu_usage = end_cpu - start_cpu
            # TODO: Inaccurate, doesn't provide much information.
            ram_usage_mb = (end_ram - start_ram) / (1024 ** 2)

            function_name = func.__name__
            execution_time = f"{elapsed_time:.4f}"
            cpu_usage_change = f"{cpu_usage:.2f}"
            ram_usage_change = f"{ram_usage_mb:.2f}"

            Global.Post("function_trace", [
                result,
                function_name,
                execution_time,
                cpu_usage_change,
                ram_usage_change,
                function_arguments
            ])

            return result

        return wrapper

class Global:
    '''Configurator and less specific functions lie here.'''

    def Post(category, data_list):
        '''
        1. Sorts string data into JSON.
        2. POSTs data to a destination API.

        Processes the following categories:
            function_trace
            arguments
            bandwidth
            device
            program_usage
        '''

        #----------------#
        # function_Trace #
        #----------------#
        if category == "function_trace":
            result = data_list[0]
            function_name = data_list[1]
            execution_time = data_list[2]
            cpu_usage_change = data_list[3]
            ram_usage_change = data_list[4]
            function_arguments = data_list[5]

            if isinstance(result, bytes):
                result_serialized = base64.b64encode(result).decode('ascii')
            else:
                try:
                    json.dumps(result)
                    result_serialized = result
                except TypeError:
                    result_serialized = str(result)

            data = {
                "result": result_serialized,
                "function_name": function_name,
                "execution_time": execution_time,
                "cpu_usage_change": cpu_usage_change,
                "ram_usage_change": ram_usage_change,
                "function_arguments": function_arguments
            }
        #-----------#
        # arguments #
        #-----------#
        elif category == "arguments":
            arguments = data_list[0]
            data = {"arguments": arguments}
        #-----------#
        # bandwidth #
        #-----------#
        elif category == "bandwidth":
            bandwidth = data_list[0]
            data = {"bandwidth": bandwidth}
        #--------#
        # device #
        #--------#
        elif category == "device":
            Language = data_list[0]
            OperatingSystem = data_list[1]
            PublicIPAddress = data_list[2]

            data = {
                "Language": Language,
                "OperatingSystem": OperatingSystem,
                "PublicIPAddress": PublicIPAddress
            }
        #---------------#
        # program_usage #
        #---------------#
        elif category == "program_usage":
            CPUUsage = data_list[0]
            RAMUsage = data_list[1]

            data = {
                "CPUUsage": CPUUsage,
                "RAMUsage": RAMUsage
            }
        else:
            data = {}

        # TODO: Move this somewhere better than in the middle of a function.
        def custom_default(o):
            if isinstance(o, bytes):
                return base64.b64encode(o).decode('ascii')
            else:
                return str(o)

        json_data = json.dumps(data, default=custom_default)
        Global.Debug(f"POST data: {json_data}")

        # Check if the queue file exists and process queued entries
        if POCKETLIFE_QUEUE.exists():
            try:
                with open(POCKETLIFE_QUEUE, 'r') as queue_file:
                    queued_entries = queue_file.readlines()
                # Attempt to post each queued JSON entry
                remaining_entries = []
                for entry in queued_entries:
                    entry = entry.strip()
                    if not entry:
                        continue
                    try:
                        Global.Debug(f"POST data: {entry}")
                        response = requests.post(
                            POCKETLIFE_HOSTNAME,
                            data=entry,
                            headers={'Content-Type': 'application/json'},
                            auth=(POCKETLIFE_USERNAME, POCKETLIFE_PASSWORD),
                            timeout=10
                        )
                        response.raise_for_status()
                        Global.Debug(f"{response.status_code}: {response.text}")
                    except requests.exceptions.RequestException as e:
                        Global.Debug(f"{response.status_code}: {response.text}")
                        remaining_entries.append(entry)
                # Overwrite the queue file with any remaining entries
                with open(POCKETLIFE_QUEUE, 'w') as queue_file:
                    for entry in remaining_entries:
                        queue_file.write(entry + '\n')
            except Exception as e:
                Global.Debug(f"Error processing queue: {e}")

        # Now attempt to post the current data
        try:
            headers = {'Content-Type': 'application/json'}
            url = POCKETLIFE_HOSTNAME
            auth = (POCKETLIFE_USERNAME, POCKETLIFE_PASSWORD)

            response = requests.post(url, data=json_data, headers=headers, auth=auth, timeout=10)
            response.raise_for_status()
            Global.Debug(f"{response.status_code}: {response.text}")
        # Exceptions that aren't important.
        except requests.exceptions.HTTPError as http_err:
            Global.Debug(f"HTTP error occurred: {http_err} - Response content: {response.text}")
            # Append failed JSON entry to the queue
            Global._append_to_queue(json_data)
        except requests.exceptions.ConnectionError as conn_err:
            Global.Debug(f"Connection error occurred: {conn_err}")
            # Append failed JSON entry to the queue
            Global._append_to_queue(json_data)
        except requests.exceptions.Timeout as timeout_err:
            Global.Debug(f"Timeout error occurred: {timeout_err}")
            # Append failed JSON entry to the queue
            Global._append_to_queue(json_data)
        # Exceptions that are "show stoppers".
        #
        # Anything printed here should also contain the Global.Name() function
        # call, as well as a quit statement.
        except NameError:
            Global.Name()
            print(f"POCKETLIFE_USERNAME, POCKETLIFE_PASSWORD, and/or POCKETLIFE_HOSTNAME undefined.")
            print(f"Quitting!")
            sys.exit(1)

    @staticmethod
    def _append_to_queue(json_data):
        '''Append failed JSON entry to the queue file.'''
        try:
            # Ensure the queue directory exists
            POCKETLIFE_QUEUE.parent.mkdir(parents=True, exist_ok=True)
            with open(POCKETLIFE_QUEUE, 'a') as queue_file:
                queue_file.write(json_data + '\n')
            Global.Debug("Data appended to queue file.")
        except Exception as e:
            Global.Debug(f"Error appending data to queue: {e}")

    def Configure(username, password, hostname):
        '''
        Assigns username/password/hostname to global variables. Mandatory function.
        '''
        global POCKETLIFE_USERNAME, POCKETLIFE_PASSWORD, POCKETLIFE_HOSTNAME
        POCKETLIFE_USERNAME = username
        POCKETLIFE_PASSWORD = password
        POCKETLIFE_HOSTNAME = hostname

    def Debug(message):
        '''
        Enables debug print statements. Toggled using the DEBUG global variable.
        '''
        if DEBUG:
            print(str(message))

    def Name():
        '''Prints the name and description of the program.'''
        print("pocketlife: A telemetry system for use in Python programs.")
