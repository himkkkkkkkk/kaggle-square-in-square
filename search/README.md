# Search agent workspace

**Agent 只能新增或修改本目录中的文件。** `puzzles.json`、`weights.json` 和评分器为只读接口；`record.json`、`aim.json` 为不可读取的私有评分数据。

## 约定

创建 `search/algorithm.py`，运行后把结果写入 `search/result.json`：

```json
{
  "10": [[-1.5, 1.5, 0.0], [-0.5, 1.5, 0.0]],
  "11": [[0.0, 0.0, 0.0]]
}
```

示例仅展示 JSON 结构，并不是合法完整布局。每个键为十进制 `n`，值为恰好 `n` 个 `[x, y, angle]`；坐标是单位正方形中心，角度使用弧度。允许只输出部分 `n`，但缺失项会受罚；不允许输出 `aim.json` 中不存在的 `n`。

从项目根目录运行：

```bash
uv run python run_search.py 10
uv run python evaluator.py --output search/score.json
```

`run_search.py` 需要 Linux `unshare`。演化控制器每次只传入一个 `n`，该进程的 imports、搜索和写出总计最多运行 10 秒；某个 n 超时后，控制器跳过后续更大的 n，并将这些 n 恢复为本轮开始时的布局继续评分。算法通过 `sys.argv[1]` 读取 `n`，单 n 更新 `incumbents.json` 时必须保留其他键。沙箱禁网、使用独立 PID 和临时 `/tmp`；用户目录只读，只有 `search/` 可写。不限制源码长度。

## 可用接口

```python
import json
from pathlib import Path
from evaluator import evaluate_layout

root = Path(__file__).resolve().parents[1]
puzzles = json.loads((root / "puzzles.json").read_text())
result = evaluate_layout(10, layout)
if result.valid:
    print(result.side_length)  # 高精度测量值
else:
    print(result.reason)
```

- `evaluator.evaluate_layout(n, layout)`：复用项目的高精度判别器，返回 `PuzzleResult(valid, side_length, score, reason)`。
- `evaluator.score_layouts(layouts, targets, weights=None)`：对内存中的布局评分并返回完整字典。
- `evaluator.score_file(...)`：从 JSON 文件评分。
- `squares_metric`：底层几何、重叠验证与官方形式评分接口。

算法可以读取并更新自己生成的 `search/incumbents.json`，从上一轮最佳合法布局继续搜索；控制器另存 `evolution/best_layouts.json`，候选失败或被拒绝时同步回滚源码和布局。停滞题权重每轮乘 1.01，保留改进后重置为 1；每 5 轮的代码审查只接受保持分数与合法性的精简实现。`puzzles.json` 只包含允许处理的 `n`。`record.json` 和 `aim.json` 是私有评分数据，已在 sandbox 中屏蔽，agent 不得读取、重建或将其布局作为初始化解。LLM 反馈仅包含合法性、权重和分数差距，不包含目标边长或目标布局。新布局必须通过 `evaluate_layout` 的严格校验。
