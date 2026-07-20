# Cloud Run-ready 컨테이너. (HF Spaces는 자체 빌드라 이 파일이 불필요 — 일반 클라우드 배포용.)
# 배포는 과금 계정이 필요하므로 미적용이지만, "카드만 연결하면 그대로 뜨는 구조"를 코드로 증명한다.
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run은 $PORT(기본 8080)로 트래픽을 보낸다. app.py가 이를 읽어 리슨한다.
ENV PORT=8080
EXPOSE 8080

CMD ["python", "app.py"]
