Below is a blueprint for a **store‑and‑forward HTTP(S) proxy** that sits on your air‑gapped host, writes every request to a shared disk, and blocks until a matching response file—produced by a relay on an Internet‑connected machine—appears.  The design leans on well‑worn patterns (forward‑proxy semantics, atomic renames, etc.) and can be built either by **extending mitmproxy** or **rolling a small asyncio proxy**.  Code sketches are included.

---

## How the bridge works (high‑level)

1. **Client → Local proxy (air‑gapped)**
   Client software (e.g. `requests`, a browser, `apt`, etc.) is pointed at `HTTP_PROXY=http://127.0.0.1:8888`.
   Because `requests` honours these env‑vars by default (`Session.trust_env == True`) all traffic flows through the proxy without code changes. ([Stack Overflow][1])

2. **Proxy serialises the flow to disk**
   It writes `/shared/requests/<uuid>.json` using **atomic rename** so half‑written files are never observed. ([Stack Overflow][2])

3. **Relay daemon (Internet‑host) consumes the file**
   A watcher on the same shared directory picks up the JSON, makes the real outbound request, and saves `/shared/responses/<uuid>.json`.
   Store‑and‑forward gateways like this are a known pattern in REST/proxy design. ([Stack Overflow][3])

4. **Air‑gapped proxy sees the response file, reconstructs the HTTP exchange, and releases the client**.

Because only files cross the gap, every transaction is durable, timestamped, and auditable; nothing “sneaks” past the proxy the way raw sockets or QUIC traffic could with a conventional network link. ([Wikipedia][4])

---

## Option A – Use **mitmproxy** with a custom addon

Mitmproxy already exposes every flow object to Python addons, and can write/read flow dumps (`-w dump`, `mitmproxy -nr dump`) out‑of‑the‑box. ([mitmproxy][5], [docs.mitmproxy.org][6])

### Sketch of an addon (`disk_bridge.py`)

```python
from mitmproxy import ctx, http
from pathlib   import Path
import json, uuid, os, time

REQ_DIR = Path("/shared/requests")
RESP_DIR = Path("/shared/responses")
RESP_TIMEOUT = 300        # seconds

def request(flow: http.HTTPFlow) -> None:
    rid = str(uuid.uuid4())
    req_path = REQ_DIR / f"{rid}.json.tmp"
    final    = REQ_DIR / f"{rid}.json"

    with req_path.open("w") as fh:
        json.dump(flow.get_state(), fh)
    os.rename(req_path, final)           # atomic publish

    # busy‑wait (or in production, use inotify/poll/select)
    start = time.time()
    resp_path = RESP_DIR / f"{rid}.json"
    while not resp_path.exists():
        if time.time()-start > RESP_TIMEOUT:
            flow.response = http.HTTPResponse.make(504, b"relay timeout")
            return
        time.sleep(0.2)

    with resp_path.open() as fh:
        flow.response = http.HTTPFlow.from_state(json.load(fh)).response
```

Run mitmproxy headless:

```bash
mitmdump -s disk_bridge.py -p 8888
```

*Pros*: TLS handling, HTTP/2 parsing, filtering rules, rich logging, tons of addons.
*Cons*:  Mitmproxy is >100 kLoC, pulls in OpenSSL, and your addon must mirror its internal flow serialisation format. ([Bad Gateway][7])

---

## Option B – Write a **minimal asyncio proxy**

A few hundred lines are enough for CONNECT‑tunnelling TLS and plain HTTP/1.1.  Public gists and Stack Overflow answers show the core pattern—`start_server`, parse first line, `open_connection`, then `asyncio.gather` two pipes. ([Gist][8], [Stack Overflow][9])

Below is a distilled, disk‑buffering handler (error‑checking stripped for clarity):

```python
# disk_proxy.py  (Python 3.11+)
import asyncio, uuid, json, os, time, pathlib, re

SHARED = pathlib.Path("/shared")
REQ, RESP = SHARED/"requests", SHARED/"responses"
for d in (REQ, RESP): d.mkdir(parents=True, exist_ok=True)

HTTP_LINE = re.compile(rb"(?P<method>\S+)\s+(?P<url>\S+)\s+HTTP/")
CONNECT   = b"CONNECT"

async def handle(reader, writer):
    head = await reader.readuntil(b"\r\n\r\n")
    rid  = str(uuid.uuid4())
    tmp  = REQ / f"{rid}.tmp"
    with tmp.open("wb") as fh:
        fh.write(head + await reader.read())          # slurp body if any
    os.rename(tmp, REQ / f"{rid}.json")               # atomic publish

    # wait for relay
    resp_file = RESP / f"{rid}.json"
    while not resp_file.exists():
        await asyncio.sleep(0.2)

    resp = json.loads(resp_file.read_bytes())
    writer.write(bytes(resp))                         # already raw HTTP
    await writer.drain()
    writer.close()

async def main():
    server = await asyncio.start_server(handle, "127.0.0.1", 8888)
    async with server: await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
```

*Enhancements you’ll want*

* **Atomic‑renames** (already used) prevent half‑written JSON from being consumed. ([Stack Overflow][2])
* **Chunked response handling** for large bodies.
* **Thread‑safe directory watching** (inotify/FSEvents) instead of polling.
* **Transparent mode**: combine with `iptables TPROXY` to capture clients that don’t honour proxy variables. ([Stack Overflow][10], [Server Fault][11])
* **Audit logging**: write a second immutable log file per flow.

---

## Relay daemon (non‑air‑gapped side)

```python
# relay.py
import requests, json, pathlib, time, os
from urllib.parse import urlsplit

SHARED=pathlib.Path("/shared")
for p in (SHARED/"requests", SHARED/"responses"): p.mkdir(exist_ok=True)

while True:
    for req_path in (SHARED/"requests").glob("*.json"):
        rid = req_path.stem
        resp_path = SHARED/"responses"/f"{rid}.json"
        if resp_path.exists(): continue

        req = json.loads(req_path.read_bytes())
        url = req["request"]["url"]  # relies on mitmproxy‑style state

        r = requests.request(req["request"]["method"], url,
                             headers=req["request"]["headers"],
                             data=req["request"]["content"],
                             verify=True, timeout=30)

        tmp = resp_path.with_suffix(".tmp")
        tmp.write_bytes(r.raw.read())    # write raw HTTP bytes if desired
        os.rename(tmp, resp_path)
    time.sleep(0.1)
```

The relay can run inside a container that has normal outbound Internet reach.  Because it sees plain JSON, you can enforce **allow‑lists**, scrub sensitive headers, or log hashes for tamper‑evidence.

---

## Security & auditing notes

| Risk                                    | Mitigation                                                                                                    |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Protocol escape (UDP/QUIC, raw TCP)** | All sockets are forced through a proxy port; unproxied protocols never reach the disk. ([Radware][12])        |
| **Malware exfiltration**                | Flows are JSON‑encoded and validated; you can checksum and sign both directions.                              |
| **Proxy compromise**                    | Constrain with SELinux/AppArmor so it may only read `/shared/requests` and write `/shared/responses`.         |
| **Covert side‑channels**                | eBPF syscall trace on the proxy PID lets you audit that it never opens unexpected FDs. ([Falco][13])          |
| **Transparent bypass**                  | Use `iptables` + `TPROXY` to redirect all outbound 80/443 to 8888. ([Stack Overflow][10], [Server Fault][11]) |

---

## When to choose each path

| Criterion         | **mitmproxy addon**        | **hand‑rolled asyncio proxy** |
| ----------------- | -------------------------- | ----------------------------- |
| TLS/HTTP2 parsing | built‑in support           | you must implement            |
| Extensibility     | full scripting API, Web UI | write Python code             |
| Binary size       | \~50 MB container          | < 1 MB                        |
| Throughput        | high (async C extensions)  | depends on your code          |
| Auditability      | bigger codebase to audit   | minimal surface               |

---

### Final thoughts

With either approach you get **deterministic, file‑level control** over every HTTP(S) transaction leaving or entering an otherwise air‑gapped system.  Because flows persist on disk you can replay them for testing, hash them for integrity, or feed them into external auditors—something a live TCP proxy cannot provide.  Tight filesystem ACLs and kernel tracing round out the security story, giving you a practical “network escrow” that is as slow or as strict as you like.

[1]: https://stackoverflow.com/questions/51887784/using-aiohttp-with-proxy?utm_source=chatgpt.com "Using Aiohttp with Proxy - python - Stack Overflow"
[2]: https://stackoverflow.com/questions/2333872/how-to-make-file-creation-an-atomic-operation?utm_source=chatgpt.com "How to make file creation an atomic operation? - Stack Overflow"
[3]: https://stackoverflow.com/questions/17960538/store-and-forward-http-requests-with-retries?utm_source=chatgpt.com "Store and forward HTTP requests with retries? - proxy - Stack Overflow"
[4]: https://en.wikipedia.org/wiki/Air_gap_%28networking%29?utm_source=chatgpt.com "Air gap (networking) - Wikipedia"
[5]: https://discourse.mitmproxy.org/t/how-save-all-request-and-response-to-a-file/525 "How save all request and response to a file? - help - mitmproxy"
[6]: https://docs.mitmproxy.org/stable/addons/examples/ "Examples"
[7]: https://lucaslegname.github.io/mitmproxy/2020/11/04/mitmproxy-scripts.html?utm_source=chatgpt.com "Creating scripts for mitmproxy - Bad Gateway"
[8]: https://gist.github.com/2minchul/609255051b7ffcde023be93572b25101 "Python HTTPS proxy server with asyncio streams · GitHub"
[9]: https://stackoverflow.com/questions/46413879/how-to-create-tcp-proxy-server-with-asyncio "python - How to create TCP proxy server with asyncio? - Stack Overflow"
[10]: https://stackoverflow.com/questions/10595575/iptables-configuration-for-transparent-proxy?utm_source=chatgpt.com "IPTables configuration for Transparent Proxy [closed] - Stack Overflow"
[11]: https://serverfault.com/questions/880441/local-transparent-proxy?utm_source=chatgpt.com "Local transparent proxy - iptables - Server Fault"
[12]: https://www.radware.com/cyberpedia/application-delivery/forward-proxy/ "
	What is a Forward Proxy: A Comprehensive Guide | Radware
"
[13]: https://falco.org/blog/tracing-syscalls-using-ebpf-part-1/?utm_source=chatgpt.com "Tracing System Calls Using eBPF - Part 1 - Falco"
