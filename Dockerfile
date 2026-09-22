FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CHIMERA_HOST=0.0.0.0 CHIMERA_PORT=8080
WORKDIR /opt/chimera
COPY chimera/ /opt/chimera/chimera/
COPY web/ /opt/chimera/web/
USER 65532:65532
EXPOSE 8080
CMD ["python", "-m", "chimera.product"]
