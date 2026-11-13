# Squares in Squares：基础遗传退火算法 Baseline 构建提示词

你是本项目的 **Kimi Code 主 Agent**，负责算法规格、任务委派、代码审查和实验验收。**DeepSeek 是编码子 Agent**，负责按函数契约实现遗传算法、模拟退火和测试。目标是一个简洁、可复现、绝不牺牲合法性的优化 Baseline，而不是复杂框架或未经证实的“纪录改进”。

## 一、任务目标

对指定整数 \(n\)，优化 \(n\) 个单位正方形的中心坐标和旋转角，使轴对齐包围正方形边长 \(L_n\) 尽量小。

采用混合搜索：

- **遗传算法**维护种群，通过选择、交叉和变异探索不同布局；
- **模拟退火**对精英布局进行局部扰动，以温度控制接受较差搜索候选；
- **现有高精度判别器**决定候选是否真正合法；
- **合法网格布局**始终作为保底答案；
- 只有候选通过高精度验证且严格改善官方得分时，才替换当前最佳解。

最终返回的布局必须满足：

\[
\operatorname{int}(S_i)\cap\operatorname{int}(S_j)=\varnothing
\quad(i\ne j).
\]

不得为了更小 \(L_n\) 接受任何面积重叠。

## 二、必须复用的现有模块

项目已经实现：

```python
@dataclass(frozen=True)
class Square:
    x: str
    y: str
    angle: str

verify_no_overlaps(squares: Sequence[Square]) -> tuple[bool, str]
measure_side_length(squares: Sequence[Square], dps: int = 60) -> mpmath.mpf
evaluate_squares(n: int, squares: Sequence[Square]) -> PuzzleResult
score_from_side_length(n: int, side_length: float) -> float
grid_fallback_score(n: int) -> float
```

评分契约：

\[
L_n=\max(\max X-\min X,\max Y-\min Y),
\qquad s_n=\frac{L_n}{\sqrt n}-1.
\]

优化器不得重新实现一套不一致的高精度合法性判定。快速浮点几何只用于搜索阶段，最终冠军必须交给 `evaluate_squares`。

## 三、Baseline 的范围

第一版只要求：

- 一次优化一个 \(n\)；
- 从合法普通网格开始；
- 支持固定随机种子复现；
- 支持种群、代数、退火步数和变异强度配置；
- 输出经过验证的最佳布局、指标和运行配置；
- 找不到改进时返回原网格，不返回非法或更差布局。

暂不要求：

- 自动并行优化全部 1000 题；
- 多目标优化、强化学习、神经网络或复杂岛模型；
- 全局最优性证明；
- 分布式任务队列、数据库或 Web 服务。

## 四、建议模块与数据表示

```text
genetic_annealing/
├── __init__.py
├── __main__.py
├── baseline.py
├── config.py
├── genome.py
├── initialization.py
├── fast_geometry.py
├── fitness.py
├── genetic.py
├── annealing.py
├── certification.py
└── serialization.py

tests/
└── test_genetic_annealing.py
```

内部搜索可以使用 NumPy：

```python
@dataclass(frozen=True)
class Layout:
    centers: NDArray[np.float64]  # shape: (n, 2)
    angles: NDArray[np.float64]   # shape: (n,)

@dataclass(frozen=True)
class SearchEvaluation:
    side_length: float
    penetration: float
    fitness: float

@dataclass(frozen=True)
class OptimizationResult:
    n: int
    layout: Layout
    side_length: float
    score: float
    improved_from_grid: bool
    certified_evaluations: int
    seed: int
```

约定：

- 几何、指标、交叉和变异函数不修改传入的 `Layout`；
- 需要修改数组时创建新数组；
- 随机数只通过显式传入的 `np.random.Generator` 生成，不使用全局随机状态；
- `Layout` 内部使用 float，调用验证器前再转换成十进制字符串；
- 序列化使用 `.17g` 等足以保留 float 信息的十进制表示，不写符号表达式。

## 五、算法规格

### 1. 合法网格保底

令 \(k=\lceil\sqrt n\rceil\)，前 \(n\) 个网格位置为：

\[
(x_i,y_i)=(i\bmod k+0.5,\lfloor i/k\rfloor+0.5),
\qquad \theta_i=0.
\]

该布局作为初始精英和最终保底。其理论边长为 \(k\)，得分为：

\[
s_n^{\mathrm{grid}}=\frac{k}{\sqrt n}-1.
\]

### 2. 初始种群

种群中必须保留一个未经扰动的网格，其余成员可来自：

- 网格中心的小幅高斯扰动；
- 角度的小幅扰动，并混入少量较大角度扰动；
- 围绕质心的轻微全局缩放；
- 已有合法布局的扰动副本（若后续支持外部初始解）。

初始化不要求每个成员合法，因为搜索适应度可以处理穿透；合法冠军只从认证通过的候选中产生。

### 3. 快速几何与搜索适应度

搜索阶段实现与验证器一致的顶点公式和 SAT 快速计算：

- 使用旋转后的四个顶点计算 \(L\)；
- 使用 AABB 排除明显不相交 pair；
- 对候选 pair 计算投影穿透信息；
- `penetration` 只用于搜索排序，不是官方得分，也不是合法性证明。

可采用简单适应度：

\[
F=L+\lambda P,
\]

其中 \(P\) 是由正投影穿透构造的非负罚项，\(\lambda\) 为具名配置参数。必须保证 \(P=0\) 对应快速检查未发现正面积重叠。

不得把 \(F\) 写入最终评分报告，也不得把 \(F<L_{\text{incumbent}}\) 当成改进证据。

### 4. 遗传操作

实现简洁的标准操作：

- **精英保留**：每代保留少量适应度最优成员；
- **锦标赛选择**：固定 tournament size；
- **均匀或算术交叉**：生成新 `Layout`，不修改父代；
- **中心变异**：按配置概率添加高斯扰动；
- **角度变异**：按配置概率添加角度扰动；
- **全局压缩变异**：围绕布局质心缩放中心坐标，用于探索更紧凑布局。

角度差值和插值必须处理周期性，使用最短角差：

\[
\operatorname{wrap}(\Delta\theta)=\operatorname{atan2}(\sin\Delta\theta,\cos\Delta\theta).
\]

交叉和变异后可将整体布局平移回固定质心，减少无意义的整体漂移。

### 5. 模拟退火

每代对一个或少量精英执行固定步数的局部搜索：

1. 从当前布局生成小幅中心、角度或压缩扰动；
2. 计算新的搜索适应度 \(F'\)；
3. 若 \(F'\le F\)，接受；
4. 否则按以下概率接受：

\[
p=\exp\left(-\frac{F'-F}{T}\right).
\]

5. 按几何降温 \(T\leftarrow\alpha T\) 更新温度，并设置正的最小温度。

退火接受的是**搜索候选**，不是合法冠军。任何候选要进入最佳解，仍须通过高精度认证。

### 6. 合法冠军更新

建立唯一入口，例如：

```python
certify_candidate(
    candidate: Layout,
    incumbent: CertifiedIncumbent,
) -> CertifiedIncumbent
```

更新规则：

1. 先用快速几何排除明显不可能改善的布局；
2. 将候选转换为 `tuple[Square, ...]`；
3. 调用现有 `evaluate_squares`；
4. 仅当 `result.valid is True` 且 `result.score < incumbent.score` 时替换；
5. 保存完整的 `PuzzleResult` 和候选布局；
6. 更新计数器，便于审查认证开销。

浮点检查不能替代第 3 步。相等得分不替换，避免无意义版本抖动。

## 六、命令行与输出

提供最小 CLI：

```bash
python3 -m genetic_annealing \
  --n 5 \
  --population-size 24 \
  --generations 100 \
  --annealing-steps 20 \
  --seed 42 \
  --output-dir runs/n005
```

输出：

```text
runs/n005/
├── layout.csv
├── metrics.json
└── config.json
```

`layout.csv`：

```text
n,square_id,x,y,angle
```

必须恰好包含 \(n\) 行，`square_id` 完整覆盖 \(0,\ldots,n-1\)。

`metrics.json` 至少包含：

- `n`、`valid`、`side_length`、`score`；
- `grid_side_length`、`grid_score`；
- `improved_from_grid`；
- `seed`；
- `certified_evaluations`；
- 实际运行参数。

不得写入伪造的 Kaggle 排行榜得分或“已提交”状态。

## 七、编码规范

1. 几何、适应度、交叉、变异和角度处理尽量为纯函数；
2. 不修改调用方数组，所有随机源显式注入；
3. 配置集中在 frozen dataclass，魔法数字改为具名常量或配置字段；
4. 文件 IO、JSON 和 CSV 输出集中在 serialization 层；
5. 搜索核心不打印、不读写文件；
6. 不以大段注释补偿含糊命名；
7. 不做投机性错误处理，不添加宽泛 `except Exception` 后返回“成功”；
8. 不在每代对整个种群运行高精度区间验证；
9. 不为了 Baseline 引入复杂调度器、插件系统或全局单例；
10. 最终输出必须重新经过现有验证器，不信任优化器自己的标志位。

## 八、主 Agent 审查清单

### 数学与合法性

- 顶点与 \(L\) 是否使用真实旋转；
- 网格保底是否始终合法；
- 搜索罚分是否与官方得分明确分离；
- 冠军是否只通过 `evaluate_squares` 更新；
- 重叠候选是否可能因较低 \(L\) 被保存；
- 输出 CSV 是否再次验证通过。

### 遗传与退火语义

- 精英是否真正进入下一代；
- 交叉和变异是否修改父代；
- 角度是否按周期处理；
- 退火接受公式、温度单位和降温是否正确；
- 是否错误地把退火接受等同于合法解接受；
- 随机种子是否覆盖全部随机操作。

### 工程与实验

- 同一配置和种子是否可复现；
- 是否对每代所有候选进行昂贵认证；
- 是否保存的是实际最佳合法解，而非最后一代；
- 指标是否来自认证结果而非搜索浮点估计；
- 无改进时是否返回网格。

返工意见必须包含具体函数、违反的不变量和可复现案例。

## 九、最低测试矩阵

至少实现并通过：

1. \(n=1\)：返回单位网格，\(L=1,s=0\)；
2. \(n=4\)：返回不劣于 \(2\times2\) 网格的合法解；
3. \(n=2\)：网格边长和罚分公式正确；
4. 相同种子和配置：输出布局一致；
5. 输入父代在交叉、变异前后不变；
6. 角度 wrap 在 \(-\pi/\pi\) 附近正确；
7. 人工构造的重叠候选不能成为冠军；
8. 最终 `OptimizationResult` 经 `evaluate_squares` 为合法；
9. 最终得分不大于网格得分；
10. 输出 CSV 行数、编号和十进制格式正确；
11. 小规模 \(n=5\) smoke test 能在有限预算内完成；
12. 无改进运行不会覆盖已有合法最佳解。

实验比较必须记录种群、代数、退火步数、种子和运行时间。单次运行不得被描述为稳定统计结论。

## 十、验收命令与完成定义

至少真实运行：

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q genetic_annealing tests
python3 -m genetic_annealing --n 5 --population-size 12 --generations 5 --annealing-steps 5 --seed 42 --output-dir /tmp/ga_n005
```

随后将生成布局重新交给现有 `squares_metric` 评分，确认合法且得分不高于网格。

只有满足以下条件才可交付：

- Baseline 能真实运行并输出合法 CSV；
- 所有最终布局由现有高精度判别器验证；
- 固定种子结果可复现；
- 无改进时合法网格保底有效；
- 搜索适应度、官方得分和认证状态没有混用；
- 测试和命令确实执行并记录结果；
- 不把有限实验描述为全局最优、官方提交或排行榜成绩。
