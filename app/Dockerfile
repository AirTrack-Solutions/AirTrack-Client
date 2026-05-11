FROM python:3.11-slim
WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive TZ=Australia/Sydney
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
# minimal deps (plus gunicorn & DB client)
RUN apt-get update && apt-get install -y --no-install-recommends \
mariadb-client gcc build-essential libmariadb3 libmariadb-dev \
python3-dev python3-venv curl rsync tzdata netcat-openbsd git openssh-client ca-certificates \
&& rm -rf /var/lib/apt/lists/*
# Add system user for uid 1000 so Git doesn't abort
RUN echo "airtrack:x:1000:1000:AirTrack:/home/airtrack:/bin/sh" >> /etc/passwd \
    && echo "airtrack:x:1000:" >> /etc/group \
    && mkdir -p /home/airtrack \
    && chown 1000:1000 /home/airtrack
# Trust /app for git regardless of file ownership
RUN git config --system safe.directory /app
# install Python deps first for better layer caching
COPY requirements.txt /app/requirements.txt
RUN python3 -m venv /venv \
&& /venv/bin/pip install --no-cache-dir --upgrade pip \
&& /venv/bin/pip install --no-cache-dir -r /app/requirements.txt \
&& /venv/bin/pip install --no-cache-dir mariadb
ENV PATH="/venv/bin:$PATH"
RUN /venv/bin/pip install --no-cache-dir flask-wtf==1.2.1
RUN mkdir -p /app/export && chmod 0777 /app/export
# now copy the whole app (this may overwrite files from prior steps)
COPY . /app
# **fix the entrypoint script *after* the full copy** so it can't be overwritten later
RUN sed -i 's/\r$//' /app/wait-for-mariadb.sh \
&& sed -i '1s/^\xEF\xBB\xBF//' /app/wait-for-mariadb.sh \
&& chmod 0755 /app/wait-for-mariadb.sh \
&& /bin/sh -lc 'ls -l /app/wait-for-mariadb.sh && head -1 /app/wait-for-mariadb.sh'
# gunicorn will import this
EXPOSE 5000
ENTRYPOINT ["/app/wait-for-mariadb.sh"]
CMD ["/venv/bin/gunicorn","-w","2","-k","gthread","--threads","8","-b","0.0.0.0:5000","--pid","/tmp/gunicorn.pid","wsgi:app"]