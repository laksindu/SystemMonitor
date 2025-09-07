import subprocess

def get_gpu_temp_via_smi():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=gpu_name,temperature.gpu", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True
        )
        output_lines = result.stdout.strip().split('\n')
        for line in output_lines:
            if line:
                gpu_name, temp = line.split(', ')
                print(f"NVIDIA GPU ({gpu_name}): {temp} °C")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error calling nvidia-smi: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    get_gpu_temp_via_smi()
