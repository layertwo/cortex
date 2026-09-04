plugins {
    `java-library`
    id("software.amazon.smithy.gradle.smithy-jar") version "1.5.0"
}

repositories {
    mavenCentral()
}

smithy {
    outputDirectory.set(file("../build/smithy"))
}

dependencies {
    smithyBuild("software.amazon.smithy:smithy-aws-traits:1.73.0")
    smithyBuild("software.amazon.smithy:smithy-aws-apigateway-traits:1.73.0")
    smithyBuild("software.amazon.smithy:smithy-validation-model:1.73.0")
    smithyBuild("software.amazon.smithy:smithy-openapi:1.73.0")
    smithyBuild("software.amazon.smithy:smithy-aws-apigateway-openapi:1.73.0")
    smithyBuild("software.amazon.smithy.typescript:smithy-aws-typescript-codegen:0.53.0")
}

// Stage the generated TS client into the npm workspace so `npm ci` can resolve
// @cortex/client. Smithy's output layout is fixed (<projection>/<plugin>), so it
// can't emit straight to packages/client — copy it there as part of the build.
// ponytail: Copy (additive) not Sync, so a later npm ci / build:client won't get
// its node_modules + dist-* wiped when smithyBuild re-runs locally.
val stageClient by tasks.registering(Copy::class) {
    from("../build/smithy/typescript/typescript-client-codegen")
    into("../packages/client")
}

tasks.named("smithyBuild") {
    finalizedBy(stageClient)
}
