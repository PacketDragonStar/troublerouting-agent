"""测试三台 HCL 设备的 SSH 连接 + display ospf peer"""
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException

USER = "zss"
PW = "123!@#456$%^"
DEVICES = ["192.168.41.12", "192.168.41.14", "192.168.41.16"]

for ip in DEVICES:
    print(f"\n{'='*50}")
    print(f"连接 {ip} ...")
    try:
        conn = ConnectHandler(
            device_type="hp_comware", host=ip,
            username=USER, password=PW,
            conn_timeout=5, auth_timeout=5,
        )
        out = conn.send_command("display ospf peer", read_timeout=10)
        print(f"✅ {ip} 连接成功")
        print(out[:400] if out else "(display ospf peer 无输出)")
        conn.disconnect()
    except NetmikoAuthenticationException:
        print(f"❌ {ip} 认证失败——用户名或密码错误")
    except NetmikoTimeoutException:
        print(f"❌ {ip} 连接超时——设备不可达或SSH未启用")
    except Exception as e:
        print(f"❌ {ip} 错误: {e}")