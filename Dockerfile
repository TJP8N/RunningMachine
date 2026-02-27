FROM python:3.11-slim

WORKDIR /app

# Install build deps for numpy/scipy, then clean up
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY src/ src/
COPY streamlit_app/ streamlit_app/

# Install the project with UI deps
RUN pip install --no-cache-dir -e ".[ui]"

# Streamlit config: disable telemetry, set headless mode
RUN mkdir -p /root/.streamlit && \
    printf '[server]\nheadless = true\nport = 8501\naddress = "0.0.0.0"\n\n[browser]\ngatherUsageStats = false\n' \
    > /root/.streamlit/config.toml

EXPOSE 8501

# Profiles volume — persists athlete data across container restarts
VOLUME /app/streamlit_app/profiles

CMD ["streamlit", "run", "streamlit_app/app.py"]
