plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.spring)
    alias(libs.plugins.kotlin.jpa)
    alias(libs.plugins.spring.boot)
    alias(libs.plugins.spring.dependency.management)
}

kotlin {
    jvmToolchain(25)
    compilerOptions {
        freeCompilerArgs.addAll("-Xjsr305=strict")
    }
}

dependencyManagement {
    imports {
        mavenBom(
            libs.spring.modulith.bom
                .get()
                .toString(),
        )
    }
}

dependencies {
    implementation(libs.spring.boot.starter.webmvc)
    implementation(libs.spring.boot.starter.security.oauth2.resource.server)
    implementation(libs.spring.boot.starter.data.jpa)
    implementation(libs.spring.boot.starter.flyway)
    implementation(libs.spring.boot.starter.actuator)
    implementation(libs.springdoc.openapi.starter.webmvc.ui)
    implementation(libs.spring.modulith.starter.core)
    implementation(libs.jackson.module.kotlin)
    implementation(libs.kotlin.reflect)
    runtimeOnly(libs.flyway.database.postgresql)
    runtimeOnly(libs.postgresql)

    testImplementation(libs.spring.boot.starter.test)
    testImplementation(libs.spring.boot.starter.webmvc.test)
    testImplementation(libs.spring.boot.starter.security.oauth2.resource.server.test)
    testImplementation(libs.spring.boot.testcontainers)
    testImplementation(libs.spring.boot.restclient)
    testImplementation(libs.testcontainers.junit.jupiter)
    testImplementation(libs.testcontainers.postgresql)
    testImplementation(libs.spring.modulith.starter.test)
    testImplementation(libs.kotlin.test.junit5)
    testRuntimeOnly(libs.junit.platform.launcher)
}

tasks.withType<Test> {
    useJUnitPlatform()
    // Der Integrationstest importiert denselben Realm wie die lokale Dev-Umgebung.
    systemProperty("judo.realm-file", rootProject.file("infra/keycloak/realm-judo-dev.json").absolutePath)
    // API-Vertrag (ADR 0007): OpenApiContractIT vergleicht damit; `-Popenapi.update` schreibt ihn neu.
    systemProperty("judo.openapi-file", rootProject.file("api/openapi.json").absolutePath)
    systemProperty("judo.openapi-update", providers.gradleProperty("openapi.update").isPresent.toString())
    inputs.files(rootProject.file("api/openapi.json")).withPropertyName("openapiContract")
}
