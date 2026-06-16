import SwiftUI
import SwiftData

@main struct InkTutorApp: App {
    var body: some Scene {
        WindowGroup {
            HomeView()
        }
        .modelContainer(for: Sheet.self)
    }
}

#Preview {
    HomeView().modelContainer(for: Sheet.self, inMemory: true)
}
