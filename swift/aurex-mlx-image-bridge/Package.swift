// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "aurex-mlx-image-bridge",
    platforms: [.macOS(.v26)],
    products: [
        .executable(name: "aurex-mlx-inpaint", targets: ["AurexMLXInpaint"]),
        .executable(name: "aurex-mlx-colorize", targets: ["AurexMLXColorize"]),
    ],
    dependencies: [
        .package(url: "https://github.com/xocialize/mlx-lama-swift", branch: "main"),
        .package(url: "https://github.com/xocialize/mlx-ddcolor-swift", branch: "main"),
    ],
    targets: [
        .executableTarget(
            name: "AurexMLXInpaint",
            dependencies: [
                .product(name: "LaMa", package: "mlx-lama-swift"),
                .product(name: "MIGAN", package: "mlx-lama-swift"),
            ]
        ),
        .executableTarget(
            name: "AurexMLXColorize",
            dependencies: [
                .product(name: "DDColor", package: "mlx-ddcolor-swift"),
            ]
        ),
    ]
)
