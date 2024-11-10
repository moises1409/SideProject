# Start from a base image with Python and required dependencies
FROM python:3.8-slim

# Copy the application code to the container
WORKDIR /app

# Install system dependencies (ffmpeg, imagemagick, and other necessary libraries)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    libasound2 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libx264-dev \
    libvpx-dev \
    nano \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

RUN sed -i 's/<policy domain="path" rights="none" pattern="@\*"/<policy domain="path" rights="read|write" pattern="@*"/' /etc/ImageMagick-6/policy.xml && \
    sed -i '/<policy domain="path" rights="none" pattern="\/tmp\/\*"/d' /etc/ImageMagick-6/policy.xml && \
    sed -i '/<policymap>/a\  <policy domain="path" rights="read|write" pattern="\/tmp\/\*"/>' /etc/ImageMagick-6/policy.xml

COPY . .

# Install Python dependencies for your project
#RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -r requirements.txt


# Expose the port on which the Flask app runs (for example, port 5000)
EXPOSE 4000

# Run the application
CMD ["flask", "run", "--host=0.0.0.0", "--port=4000"]
#CMD ["gunicorn", "--bind", "0.0.0.0:4000", "app:app"]
