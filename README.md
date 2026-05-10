# knowledge-graph-subsystem
Responsible for knowledge extraction, entity recognition, relationship construction, and building the domain-specific knowledge graph.


第5团知识图谱开发repo


# 在您本地的终端执行，排除掉 venv、缓存和git历史等无效文件
rsync -avz --exclude 'scrapers/venv' \
           --exclude 'venv' \
           --exclude '.git' \
           --exclude '__pycache__' \
           --exclude '*.csv' \
           --exclude '*.jpg' \
           /Users/sxl/Desktop/knowledge-graph-subsystem root@47.95.4.147:/root/