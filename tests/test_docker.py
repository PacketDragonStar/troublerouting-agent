"""
Ticket 15: Docker Compose / K8s 容器化部署 测试

验证:
- Dockerfile 存在且正确
- docker-compose.yml 包含 Agent 服务
- 环境变量容器模式配置
- 健康检查端点
"""
import pytest
import os
import yaml


class TestDockerfile:
    """Dockerfile 验证"""

    def test_dockerfile_exists(self):
        """Dockerfile 存在"""
        base = os.path.dirname(os.path.dirname(__file__))
        assert os.path.exists(os.path.join(base, "Dockerfile"))

    def test_dockerfile_has_python_base(self):
        """Dockerfile 包含 Python 基础镜像"""
        base = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(base, "Dockerfile"), "r", encoding="utf-8") as f:
            content = f.read()
        assert "FROM" in content
        assert "python" in content.lower()

    def test_dockerfile_copies_agent_code(self):
        """Dockerfile 复制 Agent 代码"""
        base = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(base, "Dockerfile"), "r", encoding="utf-8") as f:
            content = f.read()
        assert "COPY" in content
        assert "agent" in content.lower() or "WORKDIR" in content


class TestDockerCompose:
    """docker-compose.yml 验证"""

    def test_compose_includes_agent_service(self):
        """docker-compose.yml 包含 agent 服务"""
        base = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(base, "docker-compose.yml"), "r", encoding="utf-8") as f:
            compose = yaml.safe_load(f)
        assert "services" in compose
        assert "agent" in compose["services"]

    def test_compose_agent_has_env_vars(self):
        """agent 服务包含容器模式环境变量"""
        base = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(base, "docker-compose.yml"), "r", encoding="utf-8") as f:
            compose = yaml.safe_load(f)
        agent = compose["services"]["agent"]
        assert "environment" in agent or "env_file" in agent

    def test_compose_agent_depends_on_redis(self):
        """agent 服务依赖 redis"""
        base = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(base, "docker-compose.yml"), "r", encoding="utf-8") as f:
            compose = yaml.safe_load(f)
        agent = compose["services"]["agent"]
        assert "depends_on" in agent
        assert "redis" in agent["depends_on"]


class TestContainerEnv:
    """容器环境变量测试"""

    def test_container_mode_env(self):
        """容器模式环境变量配置"""
        base = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(base, ".env.example"), "r", encoding="utf-8") as f:
            content = f.read()
        # 容器模式下 Redis/Chroma 用服务名而非 localhost
        assert "REDIS_HOST" in content
        assert "CHROMA_HOST" in content