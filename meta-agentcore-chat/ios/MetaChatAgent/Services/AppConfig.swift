import Foundation

enum AppConfig {
    static let apiBaseURL = "https://YOUR_API_ID.execute-api.YOUR_REGION.amazonaws.com/prod"
    static let userPoolId = "YOUR_REGION_YOUR_POOL_ID"
    static let appClientId = "YOUR_APP_CLIENT_ID"
    static let awsRegion = "us-east-1"

    static var chatURL: URL { URL(string: "\(apiBaseURL)/chat")! }
}
