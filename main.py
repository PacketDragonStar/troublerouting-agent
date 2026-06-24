"""CLI 入口——命令行启动一次网络排障"""
import asyncio
import sys
from agent.agents import run_troubleshooting


def main():
    if len(sys.argv) < 2:
        print("用法: python main.py \"故障描述\"")
        print("示例: python main.py \"核心交换机 10.0.0.1 OSPF 邻居断开\"")
        sys.exit(1)

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