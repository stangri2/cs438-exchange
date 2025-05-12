FROM python:3.9-slim

WORKDIR /app

# Copy the driver script
COPY simple_driver.py .

# Make it executable
RUN chmod +x simple_driver.py

# Command to run when container starts
# Will connect to router1 on port 9000
CMD ["python", "simple_driver.py", "router1", "9000"]