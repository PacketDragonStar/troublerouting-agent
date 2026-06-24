"""HCL SSH 连接测试——直接读取 .env 凭证，独立于 Agent"""
import os

# 手动读 .env
with open(".env", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line.startswith("DEVICE_USER="):
            user = line.split("=", 1)[1]
        if line.startswith("DEVICE_PASS="):
            pw = line.split("=", 1)[1]

device_ip = os.getenv("TEST_DEVICE", "192.168.41.88")

print(f"测试连接: {device_ip}")
print(f"用户名: '{user}'")
print(f"密码长度: {len(pw)} 字符")
print("-" * 50)

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException

try:
    c = ConnectHandler(
        device_type="hp_comware",
        host=device_ip,
        username=user,
        password=pw,
        conn_timeout=5,
        auth_timeout=5,
    )
    output = c.send_command("display version", read_timeout=10)
    print("✅ SSH 连接成功！设备版本：")
    print(output[:500])
    c.disconnect()
except NetmikoAuthenticationException as e:
    print(f"❌ 认证失败——用户名或密码错误")
    print(f"   {e}")
except NetmikoTimeoutException:
    print(f"❌ 连接超时——设备 {device_ip} 不可达或 SSH 服务未启用")
except Exception as e:
    print(f"❌ 其他错误: {e}")