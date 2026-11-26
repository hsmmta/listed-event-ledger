"""运行公开虚构样例的回归测试，保存独立的历史报告。"""
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    log = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "eval"), pattern="test_*.py", top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    now = datetime.now(timezone.utc)
    report = {"运行时间UTC": now.isoformat(), "范围":"公开虚构材料规则回归。业务问答题另行人工核对。",
              "用例数": result.testsRun, "失败": len(result.failures), "错误": len(result.errors),
              "详情": log.getvalue()}
    path = ROOT / "eval" / "reports" / (now.strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(log.getvalue(), path)
    raise SystemExit(0 if result.wasSuccessful() else 1)
