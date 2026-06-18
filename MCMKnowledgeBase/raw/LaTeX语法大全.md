# LaTeX语法大全

LaTeX 是一款专业的文档排版系统，通过标记命令来描述文档结构，尤其擅长学术论文、书籍、数学公式的排版。本文档整理了 LaTeX 从入门到进阶的完整语法与常用命令，覆盖绝大多数日常使用场景。

---

## 目录

1. \[基础入门\]\(\#1\-基础入门\)

2. \[文档结构\]\(\#2\-文档结构\)

3. \[文本排版\]\(\#3\-文本排版\)

4. \[表格排版\]\(\#4\-表格排版\)

5. \[图片插入\]\(\#5\-图片插入\)

6. \[数学公式\]\(\#6\-数学公式\)

7. \[常用宏包\]\(\#7\-常用宏包\)

8. \[参考文献\]\(\#8\-参考文献\)

9. \[长文档处理\]\(\#9\-长文档处理\)

10. \[错误处理与调试\]\(\#10\-错误处理与调试\)

11. \[附录：符号速查表\]\(\#11\-附录符号速查表\)

---

## 1\. 基础入门

### 1\.1 工作流程

LaTeX 的工作流程为：

```Plain Text
.tex 源文件 → LaTeX 编译器 → PDF 输出文件
```

常用编译器：

- `pdflatex`：最常用的基础编译器

- `xelatex`：支持 Unicode 与自定义字体，适合中文排版

- `lualatex`：推荐，支持 Unicode，性能更好，兼容大部分宏包

### 1\.2 最小文档示例

```latex
% !TEX program=lualatex
\documentclass{ctexart} % 中文文章文档类
\begin{document}
Hello, world!
这是我的第一个 LaTeX 文档。
\end{document}
```

### 1\.3 文档整体结构

LaTeX 文档分为两个核心区域：

```latex
\documentclass{article} % 文档类声明（必选）
% ---------- 导言区（Preamble）----------
% 这里加载宏包、全局设置、自定义命令
\usepackage{amsmath}
\usepackage{graphicx}

% ---------- 正文区 ----------
\begin{document}
% 这里写文档的实际内容
\section{第一节}
这是正文内容。
\end{document}
% 正文区之后的内容会被忽略
```

### 1\.4 特殊字符转义

以下字符在 LaTeX 中有特殊含义，需要转义才能正常输出：

|特殊字符|转义命令|特殊字符|转义命令|
|---|---|---|---|
|`\#`|`\#`|`$`|`$`|
|`%`|`%`|`\&amp;`|`\&amp;`|
|`\{`|`\{`|`\}`|`\}`|
|`\_`|`\_`|`^`|`^\{\}`|
|`\~`|`\~\{\}`|`\\`|`\\textbackslash`|

### 1\.5 基础命令规则

- 命令以反斜线 `\\` 开头，区分大小写

- 字母命令：以非字母为结束，如 `\\section`

- 符号命令：反斜线加单个符号，如 `$`

- 必选参数：用 `\{\}` 包裹，如 `\\textbf\{文字\}`

- 可选参数：用 `\[\]` 包裹，如 `\\documentclass\[12pt\]\{article\}`

---

## 2\. 文档结构

### 2\.1 文档类

文档类定义了文档的基础类型与排版风格：

|文档类|用途|中文对应|
|---|---|---|
|`article`|短文章、论文，无章级结构|`ctexart`|
|`report`|长报告，支持章级结构|`ctexrep`|
|`book`|书籍，双面排版|`ctexbook`|
|`beamer`|演示文稿（幻灯片）|`ctexbeamer`|
|`letter`|信件|\-|

常用文档类选项：

```latex
\documentclass[12pt,twocolumn,a4paper]{ctexart}
```

- 字号：`10pt`/`11pt`/`12pt`（默认 10pt）

- 纸张：`a4paper`/`letterpaper`

- 排版：`oneside`（单面）/`twoside`（双面）/`twocolumn`（双栏）

### 2\.2 章节标题

LaTeX 提供自动编号的层级章节结构，自动写入目录：

|命令|层级|可用文档类|
|---|---|---|
|`\\part\{标题\}`|篇|全部|
|`\\chapter\{标题\}`|章|report/book/ 中文对应类|
|`\\section\{标题\}`|节|全部|
|`\\subsection\{标题\}`|小节|全部|
|`\\subsubsection\{标题\}`|子小节|全部|
|`\\paragraph\{标题\}`|段标题|全部|
|`\\subparagraph\{标题\}`|子段标题|全部|

变体用法：

- 无编号章节：`\\section\*\{标题\}`（不编号，不写入目录）

- 短标题：`\\section\[目录短标题\]\{完整长标题\}`

### 2\.3 列表环境

#### 有序列表（enumerate）

```latex
\begin{enumerate}
\item 第一项
\item 第二项
\item 第三项
\end{enumerate}
```

#### 无序列表（itemize）

```latex
\begin{itemize}
\item 苹果
\item 香蕉
\item 橙子
\end{itemize}
```

#### 描述列表（description）

```latex
\begin{description}
\item[LaTeX] 文档排版系统
\item[Python] 编程语言
\end{description}
```

#### 嵌套列表

列表最多可嵌套 4 层：

```latex
\begin{enumerate}
\item 水果
  \begin{itemize}
  \item 苹果
  \item 香蕉
  \end{itemize}
\item 蔬菜
  \begin{itemize}
  \item 白菜
  \item 萝卜
  \end{itemize}
\end{enumerate}
```

### 2\.4 目录与引用

#### 生成目录

```latex
\tableofcontents % 自动生成目录
\listoffigures   % 图片列表
\listoftables    % 表格列表
```

#### 交叉引用

通过标签实现对章节、图表、公式的自动引用：

```latex
% 在目标位置打标签
\section{引言}\label{sec:intro}
\begin{equation}\label{eq:einstein}
E=mc^2
\end{equation}

% 在其他位置引用
如第~\ref{sec:intro}节（第~\pageref{sec:intro}页）所述，
公式~\eqref{eq:einstein}是质能方程。
```

> 注意：需要编译两次才能正确解析引用，首次编译会显示`??`，属于正常现象。
> 
> 

### 2\.5 脚注与边注

```latex
正文内容\footnote{这是脚注的内容，会显示在页面底部。}
继续正文。

% 边注
正文内容\marginpar{\footnotesize 这是边注，显示在页面侧边。}
```

---

## 3\. 文本排版

### 3\.1 字体样式

|带参数命令|声明式命令|效果|
|---|---|---|
|`\\textrm\{文字\}`|`\\rmfamily`|衬线罗马体（默认）|
|`\\textsf\{文字\}`|`\\sffamily`|无衬线体|
|`\\texttt\{文字\}`|`\\ttfamily`|等宽打字机体|
|`\\textbf\{文字\}`|`\\bfseries`|**粗体**|
|`\\textit\{文字\}`|`\\itshape`|*意大利斜体*|
|`\\textsl\{文字\}`|`\\slshape`|倾斜体|
|`\\textsc\{文字\}`|`\\scshape`|小型大写字母|
|`\\emph\{文字\}`|`\\em`|强调（嵌套时自动切换）|

示例：

```latex
这是\textbf{粗体}和\textit{斜体}文字。
这是\textbf{\textit{粗斜体}}。
```

### 3\.2 字体大小

从最小到最大的字号命令：

```latex
\tiny    最小号
\scriptsize  小标注号
\footnotesize 脚注号
\small   小字号
\normalsize 默认正常号
\large   大一号
\Large   大二号
\LARGE   大三号
\huge    超大号
\Huge    最大号
```

### 3\.3 颜色

需要加载 `xcolor` 宏包：

```latex
\usepackage{xcolor}
```

基础用法：

```latex
\textcolor{red}{红色文字}
{\color{blue}蓝色文字块}
\colorbox{yellow}{黄色背景的文字}
\fcolorbox{red}{yellow}{红框黄背景的文字}
```

预定义颜色：`black`/`white`/`red`/`green`/`blue`/`cyan`/`magenta`/`yellow`/`gray`/`brown`/`orange`/`purple` 等。

自定义颜色：

```latex
\definecolor{myblue}{RGB}{0,102,204}
\textcolor{myblue}{自定义蓝色}
```

### 3\.4 间距与换行

#### 空格

|命令|宽度|说明|
|---|---|---|
|`,`|1/6em|细空格|
|`:`|2/6em|中等空格|
|`;`|5/6em|宽空格|
|`\\quad`|1em|标准空格|
|`\\qquad`|2em|双倍标准空格|
|`\!`|\-1/6em|负空格，用于紧贴|

#### 段落与行间距

```latex
\setlength{\parindent}{2em} % 首行缩进2字符
\setlength{\parskip}{0.5em} % 段落间距
\linespread{1.5} % 全局1.5倍行距
```

#### 手动断行断页

```latex
\\  % 段内换行，可加参数：\\[1cm] 额外间距
\newline % 段内换行，无参数
\noindent % 取消当前段落的首行缩进
\newpage % 手动分页
\clearpage % 分页并先处理完所有浮动体
```

\##\# 3.5 对齐环境
```latex
% 左对齐
\begin{flushleft}
左对齐的内容
\end{flushleft}

% 居中
\begin{center}
居中的内容
\end{center}

% 右对齐
\begin{flushright}
右对齐的内容
\end{flushright}
```
> 浮动体中推荐使用 `\centering` 命令，比 center 环境更少额外间距。

\##\# 3.6 超链接
需要加载 `hyperref` 宏包（建议放在导言区最后）：
```latex
\usepackage{hyperref}
\hypersetup{
  colorlinks=true, % 链接带颜色，而非边框
  linkcolor=blue, % 内部链接颜色
  citecolor=green, % 引用颜色
  urlcolor=cyan % 网址颜色
}
```

用法：
```latex
\url{https://www.overleaf.com} % 直接显示网址
\href{https://www.overleaf.com}{Overleaf在线编辑器} % 自定义显示文字
```

---

\## 4. 表格排版

\##\# 4.1 基本表格
```latex
\begin{tabular}{lcr} % 列格式：l左对齐 c居中 r右对齐
左对齐 & 居中 & 右对齐 \\
内容1 & 内容2 & 内容3 \\
内容4 & 内容5 & 内容6 \\
\end{tabular}
```

列格式说明：
| 符号 | 说明 |
|------|------|
| `l` | 左对齐 |
| `c` | 居中 |
| `r` | 右对齐 |
| `p{宽度}` | 固定宽度，自动换行 |
| `|` | 垂直分割线 |
| `*{n}{c}` | 重复n列居中，等价于cccc... |

\##\# 4.2 三线表（学术推荐）
学术论文推荐使用三线表，需要加载 `booktabs` 宏包：
```latex
\usepackage{booktabs}
```

示例：
```latex
\begin{tabular}{lcc}
\toprule
姓名 & 数学 & 语文 \\
\midrule
张三 & 95 & 88 \\
李四 & 82 & 91 \\
王五 & 90 & 85 \\
\bottomrule
\end{tabular}
```

\##\# 4.3 合并单元格
\##\## 横向合并
```latex
\multicolumn{列数}{对齐方式}{内容}
```

\##\## 纵向合并
需要加载 `multirow` 宏包：
```latex
\usepackage{multirow}
```

示例：
```latex
\begin{tabular}{ccc}
\toprule
\multirow{2}{*}{类别} & \multicolumn{2}{c}{数值} \\
\cmidrule{2-3}
& 第一列 & 第二列 \\
\midrule
A & 1 & 2 \\
B & 3 & 4 \\
\bottomrule
\end{tabular}
```

\##\# 4.4 浮动体表格
表格通常放在浮动体中，让 LaTeX 自动排版最佳位置：
```latex
\begin{table}[htbp] % 位置优先级：h这里 t顶部 b底部 p单独页
  \centering
  \caption{表格标题，自动编号}
  \label{tab:score} % 交叉引用标签
  \begin{tabular}{lcc}
    \toprule
    姓名 & 数学 & 语文 \\
    \midrule
    张三 & 95 & 88 \\
    李四 & 82 & 91 \\
    王五 & 90 & 85 \\
    \bottomrule
  \end{tabular}
\end{table}
```

---

\## 5. 图片插入

\##\# 5.1 基础用法
需要加载 `graphicx` 宏包：
```latex
\usepackage{graphicx}
% 指定图片搜索路径
\graphicspath{{figures/}{images/}}
```

插入图片：
```latex
\includegraphics{myimage.png}
```

\##\# 5.2 图片尺寸选项
```latex
% 宽度为文本宽度的80%
\includegraphics[width=0.8\textwidth]{myimage}
% 指定高度
\includegraphics[height=5cm]{myimage}
% 缩放0.5倍
\includegraphics[scale=0.5]{myimage}
% 逆时针旋转90度
\includegraphics[angle=90]{myimage}
```

\##\# 5.3 浮动体图片
```latex
\begin{figure}[htbp]
  \centering
  \includegraphics[width=0.6\textwidth]{myimage}
  \caption{图片标题}
  \label{fig:demo}
\end{figure}
```

\##\# 5.4 并排图片
```latex
\begin{figure}[htbp]
  \centering
  \includegraphics[width=0.45\textwidth]{image1}
  \qquad
  \includegraphics[width=0.45\textwidth]{image2}
  \caption{两张并排的图片}
\end{figure}
```

---

\## 6. 数学公式

数学公式是 LaTeX 的核心优势，建议加载 `amsmath` 宏包获得完整支持：
```latex
\usepackage{amsmath}
\usepackage{amssymb} % 更多数学符号
```

\##\# 6.1 公式模式
\##\## 行内公式
与文字混排，用 `$...$` 或 `<span data-type="inline-math" data-value="Li4u"></span>` 包裹：
```latex
勾股定理：$a^2 + b^2 = c^2$。
```

\##\## 行间公式（无编号）
单独占一行居中，用 `\[...\]` 包裹：
```latex
\[
\int_{-\infty}^{+\infty} e^{-x^2} dx = \sqrt{\pi}
\]
```

#### 行间公式（带编号）

使用 `equation` 环境，自动编号：

```latex
\begin{equation}\label{eq:einstein}
E = mc^2
\end{equation}
```

> 无编号版本用 `equation\*`。
> 
> 

### 6\.2 基础数学命令

#### 上下标

```latex
x^2      % 上标
a_n      % 下标
x^{2n+1} % 多字符上标
a_i^2    % 同时上下标
e^{x^2}  % 嵌套上下标
```

#### 分式与根式

```latex
\frac{a+b}{c+d} % 分式，行内自动压缩
\dfrac{a+b}{c+d} % 强制显示行间大小的分式
\sqrt{x}         % 平方根
\sqrt[3]{8}      % 三次方根
```

#### 自适应括号

使用 `\\left` 和 `\\right` 实现自动匹配大小的括号：

```latex
\[
\left( \frac{a}{b} \right)^2
\left[ \sum_{i=1}^n a_i \right]
\left\{ \frac{\partial f}{\partial x} \right\}
\left. \frac{\partial f}{\partial x} \right|_{x=0} % 单侧括号
\]
```

### 6\.3 多行公式

#### 等号对齐（align）

最常用的多行公式对齐环境，`\&amp;` 标记对齐位置：

```latex
\begin{align*} % *表示无编号
(a+b)^2 &= a^2 + 2ab + b^2 \\
(a-b)^2 &= a^2 - 2ab + b^2
\end{align*}
```

#### 分段函数（cases）

```latex
\[
|x| =
\begin{cases}
-x & \text{if } x < 0, \\
0 & \text{if } x = 0, \\
x & \text{if } x > 0.
\end{cases}
\]
```

### 6\.4 矩阵

`amsmath` 提供多种矩阵环境：

|环境|定界符|||
|---|---|---|---|
|`matrix`|无|||
|`pmatrix`|圆括号 `\(\)`|||
|`bmatrix`|方括号 `\[\]`|||
|`Bmatrix`|花括号 `\{\}`|||
|`vmatrix`|单竖线 \`|\`（行列式）||
|`Vmatrix`|双竖线 \`||\`|

示例：

```latex
\[
\mathbf{A} = \begin{pmatrix}
a_{11} & a_{12} & \cdots & a_{1n} \\
a_{21} & a_{22} & \cdots & a_{2n} \\
\vdots & \vdots & \ddots & \vdots \\
a_{n1} & a_{n2} & \cdots & a_{nn}
\end{pmatrix}
\]
```

### 6\.5 定理环境

需要加载 `amsthm` 宏包：

```latex
\usepackage{amsthm}
% 定义定理环境，编号跟随章节
\newtheorem{theorem}{定理}[section]
\newtheorem{lemma}{引理}[section]
\newtheorem{definition}{定义}[section]
```

使用示例：

```latex
\begin{theorem}[勾股定理]
直角三角形两直角边的平方和等于斜边的平方：
\[ a^2 + b^2 = c^2 \]
\end{theorem}

\begin{proof}
证明过程省略。
\end{proof}
```

### 6\.6 算法排版

常用 `algorithm2e` 宏包排版算法：

```latex
\usepackage[ruled]{algorithm2e}

\begin{algorithm}
\caption{梯度下降算法}
\label{alg:gd}
Parameters: $\eta$ 学习率\;
Initialization: $w_0$\;
\While{not converge}{
  $w_{t+1} = w_t - \eta \nabla L(w_t)$\;
}
\end{algorithm}
```

---

## 7\. 常用宏包

|宏包|功能|加载方式|
|---|---|---|
|`amsmath`|数学公式扩展|`\\usepackage\{amsmath\}`|
|`amssymb`|更多数学符号|`\\usepackage\{amssymb\}`|
|`amsthm`|定理环境|`\\usepackage\{amsthm\}`|
|`graphicx`|插入图片|`\\usepackage\{graphicx\}`|
|`geometry`|页面边距设置|`\\usepackage\{geometry\}`|
|`hyperref`|超链接与 PDF 书签|`\\usepackage\{hyperref\}`|
|`xcolor`|颜色支持|`\\usepackage\{xcolor\}`|
|`booktabs`|专业三线表|`\\usepackage\{booktabs\}`|
|`multirow`|表格跨行合并|`\\usepackage\{multirow\}`|
|`fancyhdr`|页眉页脚定制|`\\usepackage\{fancyhdr\}`|
|`caption`|图表标题定制|`\\usepackage\{caption\}`|
|`subcaption`|子图标题|`\\usepackage\{subcaption\}`|
|`listings`|代码高亮排版|`\\usepackage\{listings\}`|
|`tikz`|绘图工具|`\\usepackage\{tikz\}`|
|`float`|强制浮动体固定位置|`\\usepackage\{float\}`|
|`ulem`|下划线等文本装饰|`\\usepackage\{ulem\}`|
|`natbib`/`biblatex`|参考文献管理|`\\usepackage\{natbib\}`|
|`ctex`|中文排版支持|中文文档类已内置|

---

## 8\. 参考文献

### 8\.1 BibTeX 数据库

首先创建 `\.bib` 数据库文件，记录参考文献信息：

```bibtex
@article{einstein1905electrodynamics,
  title={Zur elektrodynamik bewegter korper},
  author={Einstein, Albert},
  journal={Annalen der physik},
  volume={17},
  number={10},
  pages={891--921},
  year={1905}
}

@book{knuth1984texbook,
  title={The TeXbook},
  author={Knuth, Donald E},
  volume={A},
  year={1984},
  publisher={Addison-Wesley}
}
```

### 8\.2 natbib 引用

```latex
\usepackage{natbib}
% 文中引用
\citet{einstein1905} % 文本引用：Einstein (1905)
\citep{einstein1905} % 括号引用：(Einstein, 1905)

% 文末生成参考文献
\bibliographystyle{plainnat}
\bibliography{mybib} % 你的bib文件名
```

### 8\.3 biblatex 引用（推荐）

```latex
\usepackage[style=authoryear]{biblatex}
\addbibresource{mybib.bib}

% 文中引用
\textcite{einstein1905}
\parencite{knuth1984}

% 文末生成
\printbibliography
```

---

## 9\. 长文档处理

### 9\.1 文件拆分

长文档可以拆分为多个文件，方便管理：

```latex
% 主文件
\documentclass{ctexbook}
\begin{document}
\frontmatter % 前言部分，罗马页码
\maketitle
\tableofcontents

\mainmatter % 正文部分，阿拉伯页码
\include{chapter1} % 导入章节，自动分页
\include{chapter2}

\appendix % 附录部分，编号变为A、B
\include{appendix}

\backmatter % 后记部分
\printbibliography
\end{document}
```

### 9\.2 选择性编译

可以只编译部分章节，加快编译速度：

```latex
\includeonly{
  chapter1,
  chapter2
}
```

---

## 10\. 错误处理与调试

### 10\.1 常见错误与解决方法

|错误信息|原因|解决方法|
|---|---|---|
|`Undefined control sequence`|命令未定义|检查拼写，或加载对应宏包|
|`Missing $ inserted`|数学符号出现在文本中|给数学内容加上`$\.\.\.$`|
|`File \&\#39;xxx\.sty\&\#39; not found`|宏包未安装|安装宏包，或检查名称拼写|
|`Too many \}\&\#39;s`|括号不匹配|检查大括号是否配对|
|`Runaway argument`|参数不匹配|检查命令的参数是否完整|
|`??`|引用未解析|再次编译文档|
|`LaTeX Error: Not in outer par mode`|浮动体放在了盒子里|给浮动体加`\[H\]`参数，或调整位置|

### 10\.2 调试技巧

1. 错误信息从上往下看，第一个错误往往是根源

2. 查看 `\.log` 日志文件获取详细错误信息

3. 遇到交互式错误，输入 `x` 退出编译

4. 复杂问题可以创建最小工作示例（MWE），只保留必要代码

---

## 11\. 附录：符号速查表

### 11\.1 希腊字母

|小写|命令|大写|命令|
|---|---|---|---|
|$\alpha$|`\\alpha`|$A$|$A$|
|$\beta$|`\\beta`|$B$|$B$|
|$\gamma$|`\\gamma`|$\Gamma$|`\\Gamma`|
|$\delta$|`\\delta`|$\Delta$|`\\Delta`|
|$\epsilon$|`\\epsilon`|$E$|$E$|
|$\theta$|`\\theta`|$\Theta$|`\\Theta`|
|$\lambda$|`\\lambda`|$\Lambda$|`\\Lambda`|
|$\mu$|`\\mu`|$M$|$M$|
|$\pi$|`\\pi`|$\Pi$|`\\Pi`|
|$\sigma$|`\\sigma`|$\Sigma$|`\\Sigma`|
|$\phi$|`\\phi`|$\Phi$|`\\Phi`|
|$\omega$|`\\omega`|$\Omega$|`\\Omega`|

### 11\.2 常用数学运算符

|符号|命令|符号|命令|
|---|---|---|---|
|$\pm$|`\\pm`|$\times$|`\\times`|
|$\div$|`\\div`|$\leq$|`\\leq`|
|$\geq$|`\\geq`|$\neq$|`\\neq`|
|$\approx$|`\\approx`|$\sum$|`\\sum`|
|$\prod$|`\\prod`|$\int$|`\\int`|
|$\partial$|`\\partial`|$\nabla$|`\\nabla`|
|$\sqrt{x}$|`\\sqrt\{x\}`|$\infty$|`\\infty`|
|$\sin$|`\\sin`|$\cos$|`\\cos`|
|$\log$|`\\log`|$\ln$|`\\ln`|

### 11\.3 箭头符号

|符号|命令|符号|命令|
|---|---|---|---|
|$\to$|`\\to`|$\gets$|`\\gets`|
|$\rightarrow$|`\\rightarrow`|$\leftarrow$|`\\leftarrow`|
|$\Rightarrow$|`\\Rightarrow`|$\Leftarrow$|`\\Leftarrow`|
|$\longrightarrow$|`\\longrightarrow`|$\longleftarrow$|`\\longleftarrow`|
|$\Longrightarrow$|`\\Longrightarrow`|$\Longleftarrow$|`\\Longleftarrow`|
|$\leftrightarrow$|`\\leftrightarrow`|$\Leftrightarrow$|`\\Leftrightarrow`|
|$\mapsto$|`\\mapsto`|$\\longmapsto\`|`\\longmapsto`|

---

## 实用工具推荐

- **在线编辑器**：[Overleaf](https://www.overleaf.com)、[TeXPage](https://www.texpage.com)

- **符号识别**：[Detexify](https://detexify.kirelabs.org) 手绘符号自动识别命令

- **社区问答**：[TeX \- LaTeX StackExchange](https://tex.stackexchange.com)

> （注：文档部分内容可能由 AI 生成）
