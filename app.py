from flask import Flask, jsonify
from flask_cors import CORS
import psutil
import platform
import math
import subprocess
import json
import shutil

HAS_WMI = False
try:
    if platform.system() == 'Windows': #This is Windows only
        import wmi
        import pythoncom
        HAS_WMI = True
except ImportError:
    print("Warning: WMI library not found. CPU/GPU temps may be disabled.")
except Exception as e:
    print(f"Error initializing WMI: {e}. Metrics may be disabled.")
    HAS_WMI = False

HAS_PYNVML = False
try:
    if platform.system() in ['Linux', 'FreeBSD']:
        from pynvml import *
        HAS_PYNVML = True
except ImportError:
    print("Warning: pynvml library not found. NVIDIA GPU stats will not be available.")
except Exception as e:
    print(f"Error initializing pynvml: {e}. GPU metrics may be disabled.")
    HAS_PYNVML = False

HAS_ROCMSMI = False
try:
    if platform.system() in ['Linux', 'FreeBSD'] and shutil.which("rocm-smi"):
        HAS_ROCMSMI = True
except Exception as e:
    print(f"Error checking for rocm-smi: {e}. AMD GPU metrics may be disabled.")
    HAS_ROCMSMI = False

app = Flask(__name__)
CORS(app)

def get_windows_hw_info():
    """Retrieves hardware info from Open Hardware Monitor on Windows."""
    cpu_temp = 0.0
    gpu_info = {}

    if HAS_WMI:
        try:
            pythoncom.CoInitialize()
            w = wmi.WMI(namespace=r"root\OpenHardwareMonitor")

            hardware_map = {}
            for hw in w.Hardware():
                hardware_map[hw.Identifier] = {
                    "name": hw.Name,
                    "type": hw.HardwareType
                }

            for sensor in w.Sensor():
                parent_identifier = sensor.Parent
                if parent_identifier in hardware_map:
                    parent_hardware = hardware_map[parent_identifier]

                    if 'CPU' in parent_hardware['type'] and sensor.SensorType == u"Temperature":
                        cpu_temp = max(cpu_temp, sensor.Value)

                    if 'Gpu' in parent_hardware['type']:
                        gpu_name = parent_hardware['name']
                        
                        name_parts = gpu_name.split()
                        if len(name_parts) >= 2 and name_parts[0] == name_parts[1]:
                            gpu_name = " ".join(name_parts[1:])

                        if gpu_name not in gpu_info:
                            gpu_info[gpu_name] = {
                                "name": gpu_name,
                                "temperature_celsius": None,
                                "usage_percent": None,
                                "memory_total_mb": None,
                                "memory_used_mb": None,
                                "memory_percent": None
                            }
                        
                        if sensor.SensorType == u"Temperature":
                            gpu_info[gpu_name]["temperature_celsius"] = sensor.Value
                        elif sensor.SensorType == u"Load" and "Core" in sensor.Name:
                            gpu_info[gpu_name]["usage_percent"] = sensor.Value
                        elif sensor.SensorType == u"Load" and "Memory" in sensor.Name:
                            gpu_info[gpu_name]["memory_percent"] = sensor.Value
                        elif sensor.SensorType == u"Data" and "Memory Total" in sensor.Name:
                            gpu_info[gpu_name]["memory_total_mb"] = sensor.Value
                        elif sensor.SensorType == u"Data" and "Memory Used" in sensor.Name:
                            gpu_info[gpu_name]["memory_used_mb"] = sensor.Value
            
            gpu_list = []
            for gpu_id, data in gpu_info.items():
                if data["temperature_celsius"] is not None and data["usage_percent"] is not None:
                    if data["memory_total_mb"] is not None and data["memory_used_mb"] is not None and data["memory_percent"] is None:
                        data["memory_percent"] = round((data["memory_used_mb"] / data["memory_total_mb"]) * 100, 2)
                    elif data["memory_total_mb"] is not None and data["memory_percent"] is not None and data["memory_used_mb"] is None:
                        data["memory_used_mb"] = round((data["memory_total_mb"] * data["memory_percent"] / 100), 2)
                    
                    gpu_list.append({
                        "name": data["name"],
                        "temperature_celsius": round(data["temperature_celsius"], 2),
                        "usage_percent": round(data["usage_percent"], 2),
                        "memory_total_mb": round(data["memory_total_mb"], 2) if data["memory_total_mb"] is not None else 0,
                        "memory_used_mb": round(data["memory_used_mb"], 2) if data["memory_used_mb"] is not None else 0,
                        "memory_percent": round(data["memory_percent"], 2) if data["memory_percent"] is not None else 0
                    })
            
            return cpu_temp, gpu_list
        except Exception as e:
            print(f"Failed to get hardware info from OHM: {e}")
            return 0.0, []
        finally:
            pythoncom.CoUninitialize()
    return 0.0, []

def get_linux_nvidia_gpu_stats():
    """Retrieves NVIDIA GPU stats using pynvml on Linux."""
    gpu_list = []
    if not HAS_PYNVML:
        return gpu_list
    try:
        nvmlInit()
        device_count = nvmlDeviceGetCount()
        for i in range(device_count):
            handle = nvmlDeviceGetHandleByIndex(i)
            gpu_name = nvmlDeviceGetName(handle).decode('utf-8')
            gpu_util = nvmlDeviceGetUtilizationRates(handle)
            gpu_temp = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
            mem_info = nvmlDeviceGetMemoryInfo(handle)
            gpu_list.append({
                "name": gpu_name,
                "usage_percent": gpu_util.gpu,
                "temperature_celsius": gpu_temp,
                "memory_total_mb": round(mem_info.total / (1024 * 1024), 2),
                "memory_used_mb": round(mem_info.used / (1024 * 1024), 2),
                "memory_percent": round(gpu_util.memory, 2)
            })
    except NVMLError as error:
        print(f"pynvml error: {error}")
    except Exception as e:
        print(f"An unexpected error occurred in get_linux_nvidia_gpu_stats: {e}")
    finally:
        try:
            nvmlShutdown()
        except NVMLError:
            pass
    return gpu_list

def get_linux_amd_gpu_stats(): #This is Linux only  
    """Retrieves AMD GPU stats using rocm-smi on Linux."""
    gpu_list = []
    if not HAS_ROCMSMI:
        return gpu_list
    try:
        cmd_output = subprocess.check_output(
            ["rocm-smi", "--json"], stderr=subprocess.STDOUT
        ).decode('utf-8')
        data = json.loads(cmd_output)
        
        for gpu_id, gpu_data in data.items():
            if "GPU" in gpu_id:
                try:
                    name = gpu_data.get("Name", "AMD GPU")
                    temp = gpu_data.get("Temperature (Sensor #1)", {}).get("Current (C)")
                    usage = gpu_data.get("GPU use (%)")
                    mem_total = gpu_data.get("VRAM Total (B)")
                    mem_used = gpu_data.get("VRAM Used (B)")
                    
                    if temp: temp = float(temp)
                    if usage: usage = float(usage)
                    if mem_total: mem_total = round(int(mem_total) / (1024 * 1024), 2)
                    if mem_used: mem_used = round(int(mem_used) / (1024 * 1024), 2)
                    
                    mem_percent = None
                    if mem_total and mem_used:
                        mem_percent = round((mem_used / mem_total) * 100, 2)
                        
                    gpu_list.append({
                        "name": name,
                        "temperature_celsius": temp,
                        "usage_percent": usage,
                        "memory_total_mb": mem_total,
                        "memory_used_mb": mem_used,
                        "memory_percent": mem_percent
                    })
                except Exception as e:
                    print(f"Error parsing rocm-smi output for {gpu_id}: {e}")
                    continue
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Failed to run rocm-smi: {e}")
    return gpu_list

@app.route('/health', methods=['GET'])
def health_check():
    """Simple endpoint to check if the server is alive."""
    return jsonify({"status": "healthy"}), 200

@app.route('/api/system_info', methods=['GET'])
def get_system_info():
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        mem_info = psutil.virtual_memory()
        disk_data = []
        partitions = psutil.disk_partitions()
        for p in partitions:
            try:
                usage = psutil.disk_usage(p.mountpoint)
                disk_data.append({
                    "device": p.device,
                    "mountpoint": p.mountpoint,
                    "total_gb": round(usage.total / (1024 * 1024 * 1024), 2),
                    "used_gb": round(usage.used / (1024 * 1024 * 1024), 2),
                    "percent": usage.percent
                })
            except Exception as e:
                print(f"Error getting disk info for {p.mountpoint}: {e}")
                continue

        cpu_temp = 0.0
        gpus = []

        if platform.system() == 'Windows':
            cpu_temp, gpus = get_windows_hw_info()
        elif platform.system() in ['Linux', 'FreeBSD']:
            try:
                temperatures = psutil.sensors_temperatures()
                if temperatures:
                    for temp_list in temperatures.values():
                        for temp_data in temp_list:
                            cpu_temp = max(cpu_temp, temp_data.current)
            except Exception as e:
                print(f"Failed to get CPU temp on Linux/FreeBSD: {e}")
            
            if HAS_PYNVML:
                gpus.extend(get_linux_nvidia_gpu_stats())
            
            if HAS_ROCMSMI:
                gpus.extend(get_linux_amd_gpu_stats())

        system_data = {
            "cpu_usage_percent": cpu_percent,
            "cpu_temperature_celsius": round(cpu_temp, 2),
            "memory_total_mb": round(mem_info.total / (1024 * 1024), 2),
            "memory_used_mb": round(mem_info.used / (1024 * 1024), 2),
            "memory_percent": mem_info.percent,
            "disks": disk_data,
            "gpus": gpus
        }

        return jsonify(system_data)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)