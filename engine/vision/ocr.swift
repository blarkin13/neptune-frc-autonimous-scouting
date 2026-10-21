// Neptune Helper text reader: Apple Vision OCR, on-device and free.
// Usage: neptune-ocr IMAGE...   Prints one JSON line per image:
//   {"file":"name.jpg","items":[{"t":"text","c":0.98,"x":0.1,"y":0.2,"w":0.05,"h":0.03}]}
// Coordinates are fractions of the image with a top-left origin.
// neptune-ocr --version prints the backend, Vision request revision and macOS version.
import Foundation
import Vision
import AppKit

let readerVersion = "1.1"
if CommandLine.arguments.dropFirst().first == "--version" {
    let os = ProcessInfo.processInfo.operatingSystemVersion
    let info: [String: Any] = ["backend": "apple-vision", "reader": readerVersion,
                               "request_revision": VNRecognizeTextRequest.currentRevision,
                               "macos": "\(os.majorVersion).\(os.minorVersion).\(os.patchVersion)"]
    print(String(data: try! JSONSerialization.data(withJSONObject: info), encoding: .utf8)!)
    exit(0)
}

for path in CommandLine.arguments.dropFirst() {
    let name = (path as NSString).lastPathComponent
    guard let image = NSImage(contentsOfFile: path),
          let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        print("{\"file\":\"\(name)\",\"error\":\"unreadable\"}")
        continue
    }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false   // team numbers and scores, not words
    request.minimumTextHeight = 0.008
    do { try VNImageRequestHandler(cgImage: cg, options: [:]).perform([request]) }
    catch { print("{\"file\":\"\(name)\",\"error\":\"vision failed\"}"); continue }
    var items: [[String: Any]] = []
    for observation in request.results ?? [] {
        guard let best = observation.topCandidates(1).first else { continue }
        let box = observation.boundingBox
        items.append(["t": best.string, "c": Double(best.confidence),
                      "x": Double(box.minX), "y": Double(1 - box.maxY),
                      "w": Double(box.width), "h": Double(box.height)])
    }
    let data = try! JSONSerialization.data(withJSONObject: ["file": name, "items": items])
    print(String(data: data, encoding: .utf8)!)
}
