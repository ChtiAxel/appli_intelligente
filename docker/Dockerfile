FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir gradio

COPY . .

ENV PYTHONPATH=/app/src
ENV GRADIO_SERVER_NAME=0.0.0.0
ENV GRADIO_SERVER_PORT=7860

EXPOSE 7860

CMD ["python", "src/NaturSQL/ui_gradio.py"]