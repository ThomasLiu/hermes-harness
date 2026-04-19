"""
pytest 配置文件
确保 hermes_harness 模块可被导入，且使用独立的测试目录
"""
import sys
import os
import tempfile
from pathlib import Path

# 在导入模块前设置 HARNESS_DIR 为临时目录
_test_harness_dir = tempfile.mkdtemp()
os.environ["HARNESS_DIR"] = _test_harness_dir

# 添加 hermes_harness 到 path
root = Path(__file__).parent.parent
sys.path.insert(0, str(root / "hermes_harness"))
