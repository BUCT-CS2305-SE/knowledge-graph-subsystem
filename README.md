# knowledge-graph-subsystem
Responsible for knowledge extraction, entity recognition, relationship construction, and building the domain-specific knowledge graph.

## Start
1. 停止服务：
```bash
pkill -f "uvicorn app:app --host 127.0.0.1 --port 8000" || true
```


2. 同步代码
```bash
rsync -avz --delete \
  --exclude ".git" \
  --exclude "venv" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude ".DS_Store" \
  ./ root@47.95.4.147:/root/knowledge-graph-subsystem/
```

3. 爬虫与入库（MVP: 只抓 Chicago，不下载图片）
```bash
ssh root@47.95.4.147
cd /root/knowledge-graph-subsystem

# 抓取并写入 MySQL（内置清洗）
python mvp/main.py

# 从 MySQL 同步到 Neo4j
python db/neo4j_builder.py
```

4. 启动服务(need refactor)
```bash
ssh root@47.95.4.147
cd /root/knowledge-graph-subsystem
nohup uvicorn app:app --host 127.0.0.1 --port 8000 > nohup.out 2>&1 &
```

5. 简单确认
```bash
# 服务器上
ps aux | grep "uvicorn app:app" | grep -v grep
tail -n 50 /root/knowledge-graph-subsystem/nohup.out
```
