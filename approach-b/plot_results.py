import json
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

with open("resultats_benchmark_B.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Ensure raw metrics exist
if "raw_metrics" not in data:
    print("No raw metrics found in JSON. Please run benchmark.py first.")
    exit(1)

metrics = data["raw_metrics"]
questions = [f"Q{i+1}" for i in range(len(metrics["latencies"]))]

# Use a nice style
plt.style.use('dark_background')
colors = sns.color_palette("husl", 8)

# 1. Performance Plot (Latency & TTFT)
fig, ax1 = plt.subplots(figsize=(10, 6))

bar_width = 0.35
index = np.arange(len(questions))

bar1 = ax1.bar(index, metrics["latencies"], bar_width, label='Total Latency (s)', color=colors[0], alpha=0.8)
bar2 = ax1.bar(index + bar_width, metrics["ttfts"], bar_width, label='TTFT (s)', color=colors[1], alpha=0.8)

ax1.set_xlabel('Questions')
ax1.set_ylabel('Time (seconds)')
ax1.set_title('Performance: Latency vs Time-To-First-Token')
ax1.set_xticks(index + bar_width / 2)
ax1.set_xticklabels(questions)
ax1.legend()

# Add value labels on top of bars
for rects in [bar1, bar2]:
    for rect in rects:
        height = rect.get_height()
        ax1.annotate(f'{height:.1f}s',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9)

plt.tight_layout()
plt.savefig("benchmark_performance.png", dpi=300)
print("Saved benchmark_performance.png")
plt.close()

# 2. Quality Plot (BLEU vs ROUGE vs F1)
fig, ax2 = plt.subplots(figsize=(10, 6))

bar1 = ax2.bar(index - bar_width, metrics["bleu"], bar_width, label='BLEU', color=colors[2])
bar2 = ax2.bar(index, metrics["rouge_l"], bar_width, label='ROUGE-L', color=colors[3])
bar3 = ax2.bar(index + bar_width, metrics["f1_overlap"], bar_width, label='F1 Overlap', color=colors[4])

ax2.set_xlabel('Questions')
ax2.set_ylabel('Score (0 to 1)')
ax2.set_title('Quality: Evaluation Scores per Question')
ax2.set_xticks(index)
ax2.set_xticklabels(questions)
ax2.legend()
ax2.set_ylim(0, max(max(metrics["bleu"]), max(metrics["rouge_l"]), max(metrics["f1_overlap"]), 0.1) * 1.2)

plt.tight_layout()
plt.savefig("benchmark_quality.png", dpi=300)
print("Saved benchmark_quality.png")
plt.close()

# 3. Throughput Plot
fig, ax3 = plt.subplots(figsize=(10, 5))
ax3.plot(questions, metrics["throughputs"], marker='o', linewidth=2, color=colors[5], markersize=8)
ax3.set_xlabel('Questions')
ax3.set_ylabel('Tokens / Second')
ax3.set_title('Generation Throughput')
ax3.grid(True, alpha=0.2)
ax3.set_ylim(0, max(metrics["throughputs"]) * 1.2)

for i, v in enumerate(metrics["throughputs"]):
    ax3.text(i, v + 1, f"{v:.1f}", ha='center', va='bottom')

plt.tight_layout()
plt.savefig("benchmark_throughput.png", dpi=300)
print("Saved benchmark_throughput.png")
plt.close()
