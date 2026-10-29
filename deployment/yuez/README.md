# BioAgent yuez Deployment

This deployment belongs to the `zhangyue` account on `172.24.195.66`.

- Checkout: `/home/zhangyue/projects/bioagent`, branch `yuez`.
- State, Python environments, Node, logs and data:
  `/home/zhangyue/.local/share/bioagent-yuez`.
- Web interface and backend: `http://172.24.195.66:8083`.
- Agent: `http://127.0.0.1:8003/v1` on the server.
- Model integration is a separate step. Provisioning never calls an LLM.

## Provision

Run these commands as `zhangyue` from the checkout:

```sh
python3 deployment/yuez/bootstrap_runtime.py
python3 deployment/yuez/install_dependencies.py
export PATH="$HOME/.local/share/bioagent-yuez/runtimes/node/bin:$PATH"
export NODE_OPTIONS=--max-old-space-size=8192
cd open-webui
npm run build
cd ..
python3 deployment/yuez/manage.py install
python3 deployment/yuez/manage.py start
python3 deployment/yuez/manage.py status
```

Python 3.11 and Node 22 are installed for this account. The Agent SDK matches
the version observed in the existing deployment. Backend packages come from
the checked-out requirements, with CPU-only PyTorch. The frontend uses its
existing npm lockfile. The install manifest and logs record actual results.

The Node download is checked against the official nodejs.org SHA256 checksum;
the uv wheel is checked against PyPI metadata. Python/npm package mirrors are
configured only in the installer process, without changing account settings.

## Operations

```sh
python3 deployment/yuez/manage.py start
python3 deployment/yuez/manage.py stop
python3 deployment/yuez/manage.py restart
python3 deployment/yuez/manage.py status
```

Only `bioagent-yuez-agent.service` and `bioagent-yuez-webui.service` are managed.
The production frontend is served by the WebUI backend. No Vite service is needed.

Private environment files are generated in the state directory's `config/`
folder with mode 0600. Existing files are preserved when installing again.
Do not commit these files or print their contents. Logs are in `logs/`.

The WebUI has its own database and login. Existing accounts and conversations
from other deployments are not imported. Offline mode prevents automatic
downloads of embedding and transcription models. These optional models,
workflow execution and Qwen inference require separate verification.
