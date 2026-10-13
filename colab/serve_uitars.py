# Colab cell: serve UI-TARS-1.5-7B via vLLM (OpenAI-compatible) behind a Cloudflare quick tunnel.
import subprocess, time, re, os
print(subprocess.run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", shell=True, capture_output=True, text=True).stdout)
subprocess.run("pip -q install vllm", shell=True)
if not os.path.exists("cloudflared"):
    subprocess.run("wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O cloudflared && chmod +x cloudflared", shell=True)
KEY = "<VLLM_API_KEY from .env>"
subprocess.Popen(f"vllm serve ByteDance-Seed/UI-TARS-1.5-7B --api-key {KEY} --max-model-len 24576 --limit-mm-per-prompt '{{\"image\": 5}}' --port 8000 > vllm.log 2>&1", shell=True)
subprocess.Popen("./cloudflared tunnel --url http://localhost:8000 > cf.log 2>&1", shell=True)
url = None
for _ in range(180):
    time.sleep(10)
    log = open("vllm.log").read()
    m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", open("cf.log").read())
    url = m.group(0) if m else url
    if "Application startup complete" in log:
        print("SWM_READY", url); break
    if "Error" in log[-3000:] and "Traceback" in log:
        print(log[-3000:]); break
else:
    print("timeout", open("vllm.log").read()[-2000:])
