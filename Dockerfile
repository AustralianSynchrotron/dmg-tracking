FROM python:3.6-alpine

WORKDIR /app

# By copying over requirements first, we make sure that Docker will cache
# our installed requirements rather than reinstall them on every build
ADD requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# Copy the service code and run it
ADD . /app

EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0"]
