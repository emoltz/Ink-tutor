import SwiftUI
import SwiftData

@main struct InkTutorApp: App {
    let container: ModelContainer

    init() {
        do {
            container = try ModelContainer(for: Sheet.self)
            seedSampleSheetIfNeeded(in: container)
        } catch {
            fatalError("Failed to create ModelContainer: \(error)")
        }
    }

    var body: some Scene {
        WindowGroup {
            HomeView()
        }
        .modelContainer(container)
    }

    private func seedSampleSheetIfNeeded(in container: ModelContainer) {
        let context = ModelContext(container)
        let count = (try? context.fetchCount(FetchDescriptor<Sheet>())) ?? 0
        guard count == 0 else { return }

        guard let url = Bundle.main.url(forResource: "Multi-Step Equations", withExtension: "pdf"),
              let pdfData = try? Data(contentsOf: url) else { return }

        context.insert(Sheet(title: "Multi Step Equations", pdfData: pdfData))
        try? context.save()
    }
}

#Preview {
    HomeView().modelContainer(for: Sheet.self, inMemory: true)
}
