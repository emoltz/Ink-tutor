import SwiftUI
import SwiftData

struct HomeView: View {
    @Environment(\.modelContext) private var context
    @Query(sort: \Sheet.createdAt, order: .reverse) private var sheets: [Sheet]
    @State private var newSheet: Sheet?

    var body: some View {
        NavigationStack {
            ScrollView {
                GlassEffectContainer(spacing: 20) {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 170), spacing: 20)], spacing: 20) {
                        ForEach(sheets) { sheet in
                            NavigationLink { CanvasEditor(sheet: sheet) } label: { SheetCard(sheet: sheet) }
                                .buttonStyle(.plain)
                                .contextMenu {
                                    Button("Delete", systemImage: "trash", role: .destructive) {
                                        context.delete(sheet)
                                    }
                                }
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("Canvases")
            .navigationDestination(item: $newSheet) { CanvasEditor(sheet: $0) }
            .overlay(alignment: .bottomTrailing) {
                Button {
                    let sheet = Sheet()
                    context.insert(sheet)
                    newSheet = sheet
                } label: {
                    Image(systemName: "plus").font(.title2.weight(.semibold)).padding(22)
                }
                .buttonStyle(.glass)
                .clipShape(.circle)
                .padding(28)
            }
        }
    }
}

struct SheetCard: View {
    let sheet: Sheet

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            RoundedRectangle(cornerRadius: 14)
                .fill(.white)
                .frame(height: 130)
                .overlay {
                    Image(systemName: sheet.pdfData == nil ? "scribble.variable" : "doc.text")
                        .font(.largeTitle).foregroundStyle(.secondary)
                }
            Text(sheet.title).font(.headline).lineLimit(1)
            Text(sheet.createdAt, style: .date).font(.caption).foregroundStyle(.secondary)
        }
        .padding(14)
        .glassEffect(in: .rect(cornerRadius: 22))
    }
}

#Preview {
    HomeView().modelContainer(for: Sheet.self, inMemory: true)
}
