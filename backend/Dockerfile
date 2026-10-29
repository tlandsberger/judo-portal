# Image des Backends (ADR 0010). Build-Kontext ist das Repo-Root:
#   docker build -f backend/Dockerfile -t judo-portal-backend .
# Tests laufen vorher in der CI, hier wird nur das Jar gebaut.

FROM eclipse-temurin:25-jdk AS build
WORKDIR /workspace
COPY gradlew settings.gradle.kts build.gradle.kts gradle.properties ./
COPY gradle gradle
COPY backend/build.gradle.kts backend/
# Gradle und Abhängigkeiten in eigenem Layer laden: bleibt bei reinen Code-Änderungen im Build-Cache.
RUN ./gradlew --no-daemon --no-configuration-cache :backend:dependencies > /dev/null
COPY backend/src backend/src
RUN ./gradlew --no-daemon :backend:bootJar \
    && java -Djarmode=tools -jar backend/build/libs/backend.jar extract --layers --destination /extracted

FROM eclipse-temurin:25-jre
LABEL org.opencontainers.image.title="judo-portal-backend" \
      org.opencontainers.image.description="WTSV Judo Portal – Backend (Spring Boot)"
RUN groupadd --system --gid 10001 portal && useradd --system --uid 10001 --gid portal --no-create-home portal
WORKDIR /app
# Layer von selten nach häufig geändert: Updates laden meist nur den kleinen Anwendungs-Layer neu.
COPY --from=build /extracted/dependencies/ ./
COPY --from=build /extracted/spring-boot-loader/ ./
COPY --from=build /extracted/snapshot-dependencies/ ./
COPY --from=build /extracted/application/ ./
USER 10001
EXPOSE 8080
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "/app/backend.jar"]
