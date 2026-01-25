FROM zaproxy/zap-stable:latest

USER root

# Increase Java heap and disable auto-update for faster startup
ENV JAVA_OPTS="-Xmx3g"

# Create startup wrapper that logs to stdout
RUN cat > /zap/start-wrapper.sh << 'WRAPPER_EOF'
#!/bin/bash
set -e
echo "========================================" >&2
echo "ZAP STARTING - $(date)" >&2
echo "========================================" >&2
echo "Memory available:" >&2
free -h >&2
echo "Java version:" >&2
java -version 2>&1 >&2
echo "Starting ZAP daemon..." >&2
exec /zap/zap.sh -daemon -host 0.0.0.0 -port 8090 \
  -config api.disablekey=true \
  -config api.addrs.addr.name=.* \
  -config api.addrs.addr.regex=true \
  -config start.checkForUpdates=false
WRAPPER_EOF

RUN chmod +x /zap/start-wrapper.sh

EXPOSE 8090

USER zap

# Start ZAP via wrapper
CMD ["/zap/start-wrapper.sh"]
