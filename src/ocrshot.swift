import Foundation
import CoreGraphics
import ImageIO
import Vision

struct OCRResult: Codable {
    let path: String
    let width: Int, height: Int
    let lines: Int, chars: Int, columns: Int
    let meanConfidence: Double
    let ms: Int
    let text: String
    let error: String?
}

struct Obs { let midY, minX, maxX, midX: CGFloat; let s: String; let c: Double }

func loadImage(_ url: URL) -> CGImage? {
    guard let src = CGImageSourceCreateWithURL(url as CFURL, nil) else { return nil }
    return CGImageSourceCreateImageAtIndex(src, 0, nil)
}

// Find vertical gutters: x-bands with no text at all. Panels in a UI are separated by these.
var gBins = 240
var gGutter = 8
var gStrategy = "leftedge"
var gMinConf = 0.30

func meaningful(_ s: String) -> Bool {
    let t = s.trimmingCharacters(in: .whitespaces)
    if t.count < 2 { return false }
    return t.rangeOfCharacter(from: CharacterSet.alphanumerics) != nil
}

func columnBounds(_ items: [Obs], bins: Int, minGutter: Int) -> [CGFloat] {
    guard items.count > 12 else { return [] }
    if gStrategy == "leftedge" {
        let xs = items.map { $0.minX }.sorted()
        var cuts: [CGFloat] = []
        for i in 1..<xs.count where xs[i] - xs[i-1] > CGFloat(minGutter) / 100.0 {
            cuts.append((xs[i] + xs[i-1]) / 2)
        }
        return cuts
    }
    var occupied = [Bool](repeating: false, count: bins)
    for it in items {
        let a = max(0, Int(it.minX * CGFloat(bins))), b = min(bins - 1, Int(it.maxX * CGFloat(bins)))
        if a <= b { for i in a...b { occupied[i] = true } }
    }
    var cuts: [CGFloat] = []
    var run = 0
    for i in 0..<bins {
        if !occupied[i] { run += 1 }
        else {
            if run >= minGutter, i - run > 0 { cuts.append(CGFloat(i) / CGFloat(bins) - CGFloat(run) / CGFloat(bins) / 2) }
            run = 0
        }
    }
    return cuts
}

func assemble(_ obs: [VNRecognizedTextObservation], tol: CGFloat, columnAware: Bool) -> (String, Int, Double, Int) {
    var items: [Obs] = []
    for o in obs {
        guard let cand = o.topCandidates(1).first else { continue }
        let b = o.boundingBox
        if Double(cand.confidence) < gMinConf { continue }
        items.append(Obs(midY: b.midY, minX: b.minX, maxX: b.maxX, midX: b.midX,
                         s: cand.string, c: Double(cand.confidence)))
    }
    guard !items.isEmpty else { return ("", 0, 0, 0) }
    let mean = items.map { $0.c }.reduce(0, +) / Double(items.count)

    let cuts = columnAware ? columnBounds(items, bins: gBins, minGutter: gGutter) : []
    var buckets: [[Obs]] = Array(repeating: [], count: cuts.count + 1)
    for it in items {
        var idx = 0
        for (k, c) in cuts.enumerated() where it.midX >= c { idx = k + 1 }
        buckets[idx].append(it)
    }

    var blocks: [String] = []
    var lineCount = 0
    for b in buckets where !b.isEmpty {
        let sorted = b.sorted { $0.midY > $1.midY }
        var groups: [[Obs]] = []
        for it in sorted {
            if let ref = groups.last?.first, abs(ref.midY - it.midY) <= tol { groups[groups.count - 1].append(it) }
            else { groups.append([it]) }
        }
        let lines = groups.map { g in g.sorted { $0.minX < $1.minX }.map { $0.s }.joined(separator: "  ") }
                          .filter(meaningful)
        lineCount += lines.count
        blocks.append(lines.joined(separator: "\n"))
    }
    return (blocks.joined(separator: "\n\n"), lineCount, (mean * 1000).rounded() / 1000, buckets.filter { !$0.isEmpty }.count)
}

var langCorrect = false
var columnAware = true
var lineTol: CGFloat = 0.008
var paths: [String] = []
var argv = Array(CommandLine.arguments.dropFirst())
var i = 0
while i < argv.count {
    switch argv[i] {
    case "--langcorrect":  langCorrect = true
    case "--no-columns":   columnAware = false
    case "--gutter":       i += 1; gGutter = Int(argv[i]) ?? 5
    case "--strategy":     i += 1; gStrategy = argv[i]
    case "--min-conf":     i += 1; gMinConf = Double(argv[i]) ?? 0.30
    case "--line-tol":     i += 1; lineTol = CGFloat(Double(argv[i]) ?? 0.008)
    default: paths.append(argv[i])
    }
    i += 1
}

var results = [OCRResult?](repeating: nil, count: paths.count)
let lock = NSLock()

DispatchQueue.concurrentPerform(iterations: paths.count) { idx in
    let p = paths[idx]
    let t0 = Date()
    guard let cg = loadImage(URL(fileURLWithPath: p)) else {
        lock.lock(); results[idx] = OCRResult(path: p, width: 0, height: 0, lines: 0, chars: 0, columns: 0,
            meanConfidence: 0, ms: 0, text: "", error: "decode failed"); lock.unlock(); return
    }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = langCorrect
    req.recognitionLanguages = ["en-US"]
    do {
        try VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
        let (text, lines, conf, cols) = assemble(req.results ?? [], tol: lineTol, columnAware: columnAware)
        let r = OCRResult(path: p, width: cg.width, height: cg.height, lines: lines, chars: text.count,
                          columns: cols, meanConfidence: conf, ms: Int(Date().timeIntervalSince(t0) * 1000),
                          text: text, error: nil)
        lock.lock(); results[idx] = r; lock.unlock()
    } catch {
        lock.lock(); results[idx] = OCRResult(path: p, width: cg.width, height: cg.height, lines: 0, chars: 0,
            columns: 0, meanConfidence: 0, ms: 0, text: "", error: "\(error)"); lock.unlock()
    }
}

let enc = JSONEncoder(); enc.outputFormatting = [.withoutEscapingSlashes]
for r in results.compactMap({ $0 }) { print(String(data: try! enc.encode(r), encoding: .utf8)!) }
