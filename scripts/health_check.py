#!/usr/bin/env python3
"""Check the health of all services and print a status summary."""

import asyncio
import subprocess

import httpx

SERVICES = {
    "api": "http://localhost:8000/health",
    "orchestrator": "http://localhost:8001/health",
    "ingestion": "http://localhost:8002/health",
    "analytics": "http://localhost:8003/health",
}

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


async def check_http(name: str, url: str) -> tuple[str, bool, str]:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(url)
            ok = r.status_code == 200
            return name, ok, f"HTTP {r.status_code}"
    except Exception as e:
        return name, False, str(e)[:60]


def check_redis() -> tuple[str, bool, str]:
    try:
        out = subprocess.check_output(["redis-cli", "ping"], timeout=3, stderr=subprocess.DEVNULL)
        ok = out.strip() == b"PONG"
        return "redis", ok, "PONG" if ok else out.decode().strip()
    except Exception as e:
        return "redis", False, str(e)[:60]


def check_postgres() -> tuple[str, bool, str]:
    try:
        out = subprocess.check_output(
            ["pg_isready", "-h", "localhost", "-p", "5432", "-U", "runtime"],
            timeout=3, stderr=subprocess.DEVNULL
        )
        ok = b"accepting" in out
        return "postgres", ok, out.decode().strip()[:60]
    except Exception as e:
        return "postgres", False, str(e)[:60]


def check_gemini_cli() -> tuple[str, bool, str]:
    try:
        out = subprocess.check_output(["gemini", "--version"], timeout=3, stderr=subprocess.STDOUT)
        version = out.decode().strip().split("\n")[0]
        return "gemini-cli", True, version
    except FileNotFoundError:
        return "gemini-cli", False, "not installed (npm install -g @google/gemini-cli)"
    except Exception as e:
        return "gemini-cli", False, str(e)[:60]


async def main() -> None:
    print(f"\n{BOLD}gemini-runtime health check{RESET}\n")

    results = []
    http_results = await asyncio.gather(*[check_http(n, u) for n, u in SERVICES.items()])
    results.extend(http_results)
    results.append(check_redis())
    results.append(check_postgres())
    results.append(check_gemini_cli())

    all_ok = True
    for name, ok, detail in results:
        status = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
        color = GREEN if ok else RED
        print(f"  {status}  {color}{name:<16}{RESET}  {detail}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print(f"{GREEN}{BOLD}All services healthy{RESET}")
    else:
        print(f"{YELLOW}Some services are not available — run 'make up' to start them{RESET}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
