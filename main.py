"""CLI 入口——命令行启动一次网络排障"""
import asyncio
import os
import sys
from agent.agents import run_troubleshooting
from agent.cmdb import CMDB
from agent.device_loader import load_devices_from_yaml

# 加载 .env 文件到 os.environ（Python 不会自动读 .env）
def _load_env_file(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if key and key not in os.environ:
                os.environ[key] = val

_load_env_file()


def main():
    if len(sys.argv) < 2:
        print("用法: python main.py \"故障描述\"")
        print("示例: python main.py \"核心交换机 10.0.0.1 OSPF 邻居断开\"")
        sys.exit(1)

    # 初始化 CMDB + 加载 devices.yml
    cmdb = CMDB()
    load_devices_from_yaml(cmdb)

    fault = sys.argv[1]
    print(f"🔍 开始排障: {fault}")
    report = asyncio.run(run_troubleshooting(fault))
    print(f"✅ 诊断完成")
    print(f"   Session ID: {report.session_id}")
    print(f"   根因: {report.root_cause}")
    print(f"   置信度: {report.confidence:.0%}")
    print(f"   风险等级: {report.risk_level}")
    print(f"   报告已保存: reports/report_{report.session_id}.md")


if __name__ == "__main__":
    main()