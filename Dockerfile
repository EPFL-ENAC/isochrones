FROM openjdk:8-jdk

WORKDIR /opt/otp

# Download OTP
RUN wget https://repo1.maven.org/maven2/org/opentripplanner/otp/1.5.0/otp-1.5.0-shaded.jar -O otp.jar

EXPOSE 8080
CMD ["java", "-Xmx2G", "-jar", "otp.jar", "--server", "--port", "8080", "--analyst", "--router", "main", "--graphs", "graphs"]
