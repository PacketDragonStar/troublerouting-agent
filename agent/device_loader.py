"""设备配置加载器——从 devices.yml 读取设备清单并注册到 CMDB"""
import os
from .cmdb import CMDB

try:
    import yaml
except ImportError:
    yaml = None


def load_devices_from_yaml(cmdb: CMDB, yaml_path: str = "devices.yml") -> int:
    """读取 devices.yml 并将设备注册到 CMDB

    Returns:
        成功加载的设备数量
    """
    if yaml is None:
        print("⚠ PyYAML 未安装，跳过 devices.yml 加载。安装: pip install pyyaml")
        return 0

    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), yaml_path)
    if not os.path.exists(path):
        print(f"⚠ {yaml_path} 不存在，跳过设备加载")
        return 0

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    count = 0
    for device in data.get("devices", []):
        cmdb.add_device(
            ip=device["ip"],
            hostname=device.get("hostname", device["ip"]),
            vendor=device.get("vendor", "cisco"),
            role=device.get("role", "access"),
        )
        count += 1

    print(f"[OK] 从 {yaml_path} 加载了 {count} 台设备到 CMDB")
    return count
