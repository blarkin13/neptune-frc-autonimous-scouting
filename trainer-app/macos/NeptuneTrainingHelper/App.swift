import AppKit
import Security
import Sparkle

let credentialLabel = "Neptune Training Helper — saved Neptune connection"
let credentialService = "com.neptunefrc.traininghelper.connection"
func saveCredential(_ data: Data) throws {
    let query: [String:Any] = [kSecClass as String:kSecClassGenericPassword,kSecAttrService as String:credentialService,kSecAttrAccount as String:"owner"]
    let status = SecItemUpdate(query as CFDictionary,[kSecValueData as String:data,kSecAttrLabel as String:credentialLabel] as CFDictionary)
    if status == errSecItemNotFound {
        var add=query;add[kSecValueData as String]=data;add[kSecAttrLabel as String]=credentialLabel;add[kSecAttrAccessible as String]=kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        guard SecItemAdd(add as CFDictionary,nil)==errSecSuccess else {throw NSError(domain:"Keychain",code:1,userInfo:[NSLocalizedDescriptionKey:"Could not save your connection in Keychain."])}
    } else if status != errSecSuccess {throw NSError(domain:"Keychain",code:Int(status),userInfo:[NSLocalizedDescriptionKey:"Allow Neptune Training Helper to access its Keychain connection."])}
}
func loadCredential() -> Data? {
    let query:[String:Any]=[kSecClass as String:kSecClassGenericPassword,kSecAttrService as String:credentialService,kSecAttrAccount as String:"owner",kSecReturnData as String:true,kSecMatchLimit as String:kSecMatchLimitOne]
    var result:CFTypeRef?;return SecItemCopyMatching(query as CFDictionary,&result)==errSecSuccess ? result as? Data:nil
}

// Draw the card behind its children using AppKit. A layer-backed background
// can cover the nested stack's text on newer macOS even while AX sees it.
@MainActor final class StatusCard: NSView {
    let fill: NSColor
    let outline: NSColor
    init(fill: NSColor, outline: NSColor) {
        self.fill = fill; self.outline = outline
        super.init(frame: .zero)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is unavailable") }
    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        let path = NSBezierPath(roundedRect: bounds.insetBy(dx: 0.5, dy: 0.5), xRadius: 12, yRadius: 12)
        fill.setFill(); path.fill()
        outline.setStroke(); path.lineWidth = 1; path.stroke()
    }
}

// Faint moving dots behind the native helper controls, matching Neptune's dashboard.
@MainActor final class AmbientBubbles: NSView {
    private var timer: Timer?
    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        if !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion {
            timer = Timer.scheduledTimer(withTimeInterval: 1.0/24.0, repeats: true) { [weak self] _ in self?.needsDisplay = true }
        }
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is unavailable") }
    deinit { timer?.invalidate() }
    override func hitTest(_ point: NSPoint) -> NSView? { nil }
    override func draw(_ dirtyRect: NSRect) {
        let time = NSWorkspace.shared.accessibilityDisplayShouldReduceMotion ? 0 : ProcessInfo.processInfo.systemUptime
        for i in 0..<25 {
            let seed = Double(i)
            let x = (seed * 0.61803398875).truncatingRemainder(dividingBy: 1.0) * max(1, bounds.width)
            let y = ((seed * 0.38196601125 + time * (0.003 + seed.truncatingRemainder(dividingBy: 5) * 0.0007)).truncatingRemainder(dividingBy: 1.0)) * max(1, bounds.height)
            let radius = CGFloat(2 + i % 4)
            let circle = NSBezierPath(ovalIn: NSRect(x: x-radius, y: y-radius, width: radius*2, height: radius*2))
            NSColor(srgbRed: 0.46, green: 0.70, blue: 0.91, alpha: 0.055).setFill();circle.fill()
            NSColor(srgbRed: 0.57, green: 0.80, blue: 0.95, alpha: 0.23).setStroke();circle.lineWidth = 0.7;circle.stroke()
        }
    }
}

@MainActor final class HardwareMeter: NSStackView {
    let value=NSTextField(labelWithString:"—")
    let bar=MeterFill()
    init(_ title:String) {
        super.init(frame:.zero);orientation = .vertical;alignment = .leading;spacing=4
        let row=NSStackView();row.distribution = .fill;row.orientation = .horizontal;row.spacing=8
        let label=NSTextField(labelWithString:title);label.textColor=NSColor(srgbRed:0.61,green:0.68,blue:0.77,alpha:1);label.font = .systemFont(ofSize:11)
        value.font = .systemFont(ofSize:11,weight:.medium);value.textColor = .white
        let space=NSView();space.setContentHuggingPriority(NSLayoutConstraint.Priority(1),for:.horizontal)
        row.addArrangedSubview(label);row.addArrangedSubview(space);row.addArrangedSubview(value);addArrangedSubview(row);addArrangedSubview(bar)
        row.widthAnchor.constraint(equalTo:widthAnchor).isActive=true;bar.widthAnchor.constraint(equalTo:widthAnchor).isActive=true;bar.heightAnchor.constraint(equalToConstant:4).isActive=true
    }
    required init?(coder:NSCoder) {fatalError("init(coder:) is unavailable")}
    func show(_ fraction:Double?,_ text:String) {value.stringValue=text;bar.fraction=fraction}
}
@MainActor final class MeterFill:NSView {
    var fraction:Double? {didSet {needsDisplay=true}}
    override func draw(_ dirtyRect:NSRect) {
        let path=NSBezierPath(roundedRect:bounds,xRadius:2,yRadius:2);NSColor(srgbRed:0.11,green:0.16,blue:0.20,alpha:1).setFill();path.fill()
        if let fraction=fraction {let r=NSRect(x:0,y:0,width:bounds.width*min(1,max(0,fraction)),height:bounds.height);NSColor(srgbRed:0.56,green:0.71,blue:0.87,alpha:1).setFill();NSBezierPath(roundedRect:r,xRadius:2,yRadius:2).fill()}
    }
}
@MainActor final class FlippedStackView:NSStackView {
    override var isFlipped:Bool {true}
}

@main @MainActor final class App: NSObject, NSApplicationDelegate, NSWindowDelegate, SPUUpdaterDelegate {
    var window:NSWindow!;var updater:SPUStandardUpdaterController!
    var helperContent:NSStackView!;var dashboard:NSView!;var dashboardBody:NSStackView!;var dashboardStatus=NSTextField(labelWithString:"Connecting to Neptune…")
    var dashboardTimer:Timer?;var dashboardLoading=false;var pinnedTop:[NSView]=[];var pinnedBottom:[NSView]=[];var thisMacCards:[NSView]=[]
    var task:Process?;var input:FileHandle?;var buffer=Data();var busy=false;var quitting=false
    var cachedCredential:Data?;var pendingCommand:String?;var installHandler:(()->Void)?;var logFile:FileHandle?
    var status=NSTextField(wrappingLabelWithString:"Connect this Mac to Neptune to begin.")
    var connection=NSTextField(wrappingLabelWithString:"Disconnected")
    var updateStatus=NSTextField(wrappingLabelWithString:"Updates are checked automatically.")
    var version=NSTextField(wrappingLabelWithString:"")
    var reviewButton:NSButton!;var reviewing=false
    var folderButton:NSButton!;var folderReview=false;var imageFolderPath:String?
    var progress=NSProgressIndicator();var remaining=NSTextField(labelWithString:"");var progressRow=NSStackView()
    var cpuMeter=HardwareMeter("CPU"),gpuMeter=HardwareMeter("GPU"),ramMeter=HardwareMeter("RAM"),vramMeter=HardwareMeter("GPU memory")
    var computerDetail=NSTextField(labelWithString:""),availability=NSTextField(labelWithString:"Connecting"),jobTitle=NSTextField(labelWithString:""),stageText=NSTextField(labelWithString:""),nextStatus=NSTextField(labelWithString:"")
    var stageProgress=NSProgressIndicator(),stageRow=NSStackView()
    var jobCardHeight:NSLayoutConstraint?,statusHeight:NSLayoutConstraint?
    var activityScroll:NSScrollView!;var activityToggle:NSButton!
    var log=NSTextView();var stop:NSButton!;var connect:NSButton!;var run:NSButton!;var device=NSPopUpButton()
    let support=FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Neptune Training Helper")
    static func main() {let app=NSApplication.shared;let delegate=App();app.delegate=delegate;app.setActivationPolicy(.regular);app.run()}
    func applicationDidFinishLaunching(_ notification:Notification) {
        try? FileManager.default.createDirectory(at:support,withIntermediateDirectories:true,attributes:[.posixPermissions:0o700])
        let logs=FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/Neptune Training Helper")
        try? FileManager.default.createDirectory(at:logs,withIntermediateDirectories:true,attributes:[.posixPermissions:0o700])
        let file=logs.appendingPathComponent("helper.log")
        if !FileManager.default.fileExists(atPath:file.path) {FileManager.default.createFile(atPath:file.path,contents:nil,attributes:[.posixPermissions:0o600])}
        logFile=try? FileHandle(forWritingTo:file);try? logFile?.seekToEnd()
        buildUI()
#if DASHBOARD_PREVIEW
        dashboardStatus.stringValue="Preview · example readouts"
        if let url=Bundle.main.url(forResource:"dashboard-fixture",withExtension:"json"),
           let data=try? Data(contentsOf:url),
           let fixture=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any] {renderDashboard(fixture)}
        return
#endif
        updater=SPUStandardUpdaterController(startingUpdater:true,updaterDelegate:self,userDriverDelegate:nil)
        DispatchQueue.main.asyncAfter(deadline:.now()+2) {self.updater.updater.checkForUpdatesInBackground()}
        connection.stringValue="Checking saved Neptune connection…"
        status.stringValue="If macOS asks for Keychain access, use your Mac login password to let this app read its saved Neptune connection."
        DispatchQueue.global().async {let saved=loadCredential();DispatchQueue.main.async {self.cachedCredential=saved;if saved != nil {self.launch("run");self.reloadDashboard()} else {self.connection.stringValue="Disconnected";self.status.stringValue="Connect this Mac to Neptune to begin.";self.append("1. Connect to Neptune. 2. Approve this Mac in your browser. 3. Choose training or a match test on Neptune.")}}}
    }
    func buildUI() {
        let ink=NSColor(srgbRed:0.07,green:0.14,blue:0.24,alpha:1)
        let panel=NSColor(srgbRed:0.09,green:0.18,blue:0.30,alpha:0.92)
        let line=NSColor(srgbRed:0.17,green:0.27,blue:0.37,alpha:1)
        let accent=NSColor(srgbRed:0.325,green:0.831,blue:0.929,alpha:1)
        let muted=NSColor(srgbRed:0.61,green:0.68,blue:0.77,alpha:1)
        window=NSWindow(contentRect:NSRect(x:0,y:0,width:1120,height:780),styleMask:[.titled,.closable,.miniaturizable,.resizable],backing:.buffered,defer:false)
        window.appearance=NSAppearance(named:.darkAqua);window.title="Neptune Training Helper"
        window.minSize=NSSize(width:640,height:460)
        window.collectionBehavior=[.fullScreenPrimary];window.delegate=self;window.backgroundColor=ink
        let root=NSStackView();root.orientation = .vertical;root.alignment = .leading;root.spacing=8
        root.edgeInsets=NSEdgeInsets(top:12,left:20,bottom:12,right:20);root.translatesAutoresizingMaskIntoConstraints=false
        helperContent=root
        let bubbles=AmbientBubbles(frame:.zero);bubbles.translatesAutoresizingMaskIntoConstraints=false
        window.contentView!.addSubview(bubbles)
        NSLayoutConstraint.activate([bubbles.leadingAnchor.constraint(equalTo:window.contentView!.leadingAnchor),bubbles.trailingAnchor.constraint(equalTo:window.contentView!.trailingAnchor),bubbles.topAnchor.constraint(equalTo:window.contentView!.topAnchor),bubbles.bottomAnchor.constraint(equalTo:window.contentView!.bottomAnchor)])
        window.contentView!.addSubview(root)
        NSLayoutConstraint.activate([root.leadingAnchor.constraint(equalTo:window.contentView!.leadingAnchor),root.trailingAnchor.constraint(equalTo:window.contentView!.trailingAnchor),root.topAnchor.constraint(equalTo:window.contentView!.topAnchor),root.bottomAnchor.constraint(equalTo:window.contentView!.bottomAnchor)])
        func card(_ height:Double)->(StatusCard,NSStackView) {
            let card=StatusCard(fill:panel,outline:line);let stack=NSStackView();stack.orientation = .vertical;stack.alignment = .leading;stack.spacing=8;stack.translatesAutoresizingMaskIntoConstraints=false;card.addSubview(stack)
            NSLayoutConstraint.activate([stack.leadingAnchor.constraint(equalTo:card.leadingAnchor,constant:12),stack.trailingAnchor.constraint(equalTo:card.trailingAnchor,constant:-12),stack.topAnchor.constraint(equalTo:card.topAnchor,constant:12),stack.bottomAnchor.constraint(equalTo:card.bottomAnchor,constant:-12)])
            thisMacCards.append(card)
            if height>0 {card.heightAnchor.constraint(equalToConstant:height).isActive=true};root.addArrangedSubview(card);return(card,stack)
        }
        var deferredWidths:[NSLayoutConstraint]=[]
        let (_,live)=card(164)
        let head=NSStackView();head.distribution = .fill;head.orientation = .horizontal;head.alignment = .centerY;head.spacing=10
        let mark=NSImageView();mark.image=Bundle.main.resourceURL.map {$0.appendingPathComponent("engine/neptune-logo-square.png")}.flatMap {NSImage(contentsOf:$0)};mark.imageScaling = .scaleProportionallyUpOrDown;mark.widthAnchor.constraint(equalToConstant:32).isActive=true;mark.heightAnchor.constraint(equalToConstant:32).isActive=true;head.addArrangedSubview(mark)
        let copy=NSStackView();copy.orientation = .vertical;copy.alignment = .leading;copy.spacing=2
        let name=NSTextField(labelWithString:Host.current().localizedName ?? "This Mac");name.font = .systemFont(ofSize:15,weight:.bold);name.textColor = .white;name.lineBreakMode = .byTruncatingTail
        computerDetail.font = .systemFont(ofSize:10);computerDetail.textColor=muted;computerDetail.stringValue="Mac · reading hardware…";computerDetail.lineBreakMode = .byTruncatingTail
        copy.addArrangedSubview(name);copy.addArrangedSubview(computerDetail);head.addArrangedSubview(copy)
        let badge=StatusCard(fill:NSColor(srgbRed:0.09,green:0.15,blue:0.23,alpha:1),outline:panel);badge.widthAnchor.constraint(equalToConstant:88).isActive=true;badge.heightAnchor.constraint(equalToConstant:25).isActive=true
        availability.font = .systemFont(ofSize:11,weight:.semibold);availability.textColor = .white;availability.alignment = .center;availability.translatesAutoresizingMaskIntoConstraints=false;badge.addSubview(availability)
        NSLayoutConstraint.activate([availability.centerXAnchor.constraint(equalTo:badge.centerXAnchor),availability.centerYAnchor.constraint(equalTo:badge.centerYAnchor)])
        head.addArrangedSubview(badge);deferredWidths.append(head.widthAnchor.constraint(equalTo:live.widthAnchor));head.heightAnchor.constraint(equalToConstant:40).isActive=true;live.addArrangedSubview(head)
        let meters=NSStackView();meters.orientation = .vertical;meters.spacing=8;meters.alignment = .leading
        for pair in [[cpuMeter,gpuMeter],[ramMeter,vramMeter]] {
            let row=NSStackView();row.orientation = .horizontal;row.distribution = .fillEqually;row.spacing=16
            for meter in pair {row.addArrangedSubview(meter)};deferredWidths.append(row.widthAnchor.constraint(equalTo:live.widthAnchor));row.heightAnchor.constraint(equalToConstant:30).isActive=true;meters.addArrangedSubview(row)
        }
        meters.heightAnchor.constraint(equalToConstant:68).isActive=true;live.addArrangedSubview(meters)
        connection.font = .systemFont(ofSize:10);connection.textColor=muted;connection.maximumNumberOfLines=1;connection.lineBreakMode = .byTruncatingTail;connection.heightAnchor.constraint(equalToConstant:16).isActive=true;live.addArrangedSubview(connection)
        let (job,jobStack)=card(0);jobCardHeight=job.heightAnchor.constraint(equalToConstant:62);jobCardHeight?.isActive=true;jobStack.spacing=6
        jobTitle.stringValue="THIS MAC";jobTitle.font = .systemFont(ofSize:10,weight:.bold);jobTitle.textColor=accent;jobTitle.heightAnchor.constraint(equalToConstant:14).isActive=true;jobTitle.maximumNumberOfLines=1;jobTitle.lineBreakMode = .byTruncatingTail;jobStack.addArrangedSubview(jobTitle)
        status.font = .systemFont(ofSize:11);status.textColor = .white;status.maximumNumberOfLines=2;status.preferredMaxLayoutWidth=536;deferredWidths.append(status.widthAnchor.constraint(equalTo:jobStack.widthAnchor))
        statusHeight=status.heightAnchor.constraint(equalToConstant:18);statusHeight?.isActive=true;status.stringValue="No assigned job";jobStack.addArrangedSubview(status)
        func progressLine(_ text:NSTextField,_ bar:NSProgressIndicator)->NSStackView {
            let box=NSStackView();box.orientation = .vertical;box.alignment = .leading;box.spacing=4;text.font = .monospacedSystemFont(ofSize:10,weight:.regular);text.textColor=muted;text.maximumNumberOfLines=1;text.lineBreakMode = .byTruncatingTail
            bar.minValue=0;bar.maxValue=100;bar.isIndeterminate=false;bar.style = .bar;deferredWidths.append(bar.widthAnchor.constraint(equalTo:jobStack.widthAnchor));box.addArrangedSubview(text);box.addArrangedSubview(bar);box.heightAnchor.constraint(equalToConstant:26).isActive=true;return box
        }
        stageRow=progressLine(stageText,stageProgress);progressRow=progressLine(remaining,progress);jobStack.addArrangedSubview(stageRow);jobStack.addArrangedSubview(progressRow)
        nextStatus.font = .systemFont(ofSize:10);nextStatus.textColor=muted;nextStatus.maximumNumberOfLines=1;nextStatus.lineBreakMode = .byTruncatingTail;nextStatus.heightAnchor.constraint(equalToConstant:12).isActive=true;jobStack.addArrangedSubview(nextStatus)
        stageRow.isHidden=true;progressRow.isHidden=true;nextStatus.isHidden=true
        let buttons=NSStackView();buttons.orientation = .horizontal;buttons.spacing=8
        run=NSButton(title:"Open Neptune",target:self,action:#selector(openSite));connect=NSButton(title:"Reconnect",target:self,action:#selector(reconnect));reviewButton=NSButton(title:"Review tracking…",target:self,action:#selector(reviewTracking))
        folderButton=NSButton(title:"Label image folder…",target:self,action:#selector(labelImageFolder))
        for button in [run!,connect!,reviewButton!,folderButton!] {button.bezelStyle = .rounded;button.font = .systemFont(ofSize:11,weight:.medium);button.heightAnchor.constraint(equalToConstant:32).isActive=true;buttons.addArrangedSubview(button)}
        run.bezelColor=accent;run.contentTintColor=ink;root.addArrangedSubview(buttons);buttons.heightAnchor.constraint(equalToConstant:32).isActive=true
        let controls=NSStackView();controls.orientation = .horizontal;controls.spacing=10
        let deviceLabel=NSTextField(labelWithString:"Training device");deviceLabel.font = .systemFont(ofSize:11);deviceLabel.textColor=muted;controls.addArrangedSubview(deviceLabel)
        device.addItems(withTitles:["Automatic","Mac GPU","CPU"]);device.selectItem(withTitle:UserDefaults.standard.string(forKey:"device") ?? "Automatic");device.target=self;device.action=#selector(changeDevice);controls.addArrangedSubview(device)
        stop=NSButton(title:"Stop after this match",target:self,action:#selector(stopMatch));stop.isEnabled=false;controls.addArrangedSubview(stop);root.addArrangedSubview(controls);controls.heightAnchor.constraint(equalToConstant:28).isActive=true
        let identity=Bundle.main.url(forResource:"engine-identity",withExtension:"json").flatMap {try? Data(contentsOf:$0)}.flatMap {try? JSONSerialization.jsonObject(with:$0) as? [String:Any]}
        let engine=(identity?["version"] as? String ?? "Unknown").components(separatedBy:"-").first ?? "Unknown"
        version.stringValue="v\(Bundle.main.object(forInfoDictionaryKey:"CFBundleShortVersionString") ?? "") · Engine \(engine)";version.font = .systemFont(ofSize:9);version.textColor=muted
        updateStatus.font = .systemFont(ofSize:9);updateStatus.textColor=muted;updateStatus.maximumNumberOfLines=1;updateStatus.lineBreakMode = .byTruncatingTail
        let footer=NSStackView();footer.orientation = .horizontal;footer.spacing=14;footer.addArrangedSubview(version);footer.addArrangedSubview(updateStatus);footer.heightAnchor.constraint(equalToConstant:26).isActive=true;root.addArrangedSubview(footer)
        activityToggle=NSButton(title:"Show activity",target:self,action:#selector(toggleActivity));activityToggle.bezelStyle = .rounded;activityToggle.font = .systemFont(ofSize:11);activityToggle.heightAnchor.constraint(equalToConstant:26).isActive=true;root.addArrangedSubview(activityToggle)
        let scroll=NSScrollView();scroll.hasVerticalScroller=true;scroll.borderType = .noBorder;scroll.documentView=log;log.isEditable=false;log.isSelectable=true;log.font = .monospacedSystemFont(ofSize:10,weight:.regular);log.textColor = .white;log.backgroundColor=ink;log.autoresizingMask=[.width];log.isVerticallyResizable=true;log.textContainer?.widthTracksTextView=true
        root.addArrangedSubview(scroll);scroll.heightAnchor.constraint(equalToConstant:180).isActive=true;activityScroll=scroll;scroll.isHidden=true
        let spacer=NSView();spacer.setContentHuggingPriority(NSLayoutConstraint.Priority(1),for:.vertical);spacer.heightAnchor.constraint(greaterThanOrEqualToConstant:0).isActive=true;root.addArrangedSubview(spacer)
        let menu=NSMenu();let item=NSMenuItem();let appMenu=NSMenu();appMenu.addItem(withTitle:"Check for Updates…",action:#selector(checkUpdates),keyEquivalent:"");appMenu.addItem(withTitle:"Import existing helper connection…",action:#selector(importConnection),keyEquivalent:"");appMenu.addItem(withTitle:"Show logs",action:#selector(showLogs),keyEquivalent:"");appMenu.addItem(.separator());appMenu.addItem(withTitle:"Quit Neptune Training Helper",action:#selector(NSApplication.terminate(_:)),keyEquivalent:"q");item.submenu=appMenu;menu.addItem(item);NSApp.mainMenu=menu
        let viewMenuItem=NSMenuItem(title:"View",action:nil,keyEquivalent:"");let viewMenu=NSMenu(title:"View")
        viewMenu.addItem(withTitle:"Refresh readouts",action:#selector(reloadDashboard),keyEquivalent:"r")
        let fullScreenItem=viewMenu.addItem(withTitle:"Enter Full Screen",action:#selector(toggleFullScreen),keyEquivalent:"f");fullScreenItem.keyEquivalentModifierMask=[.control,.command]
        viewMenuItem.submenu=viewMenu;menu.addItem(viewMenuItem)
        NSLayoutConstraint.activate(deferredWidths)
        buildDashboard(background:ink)
        dashboardTimer=Timer.scheduledTimer(withTimeInterval:10,repeats:true) {[weak self] _ in Task { @MainActor in self?.reloadDashboard() }}
        window.contentView!.layoutSubtreeIfNeeded();window.center();window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)
    }
    func buildDashboard(background:NSColor) {
        let content=window.contentView!
        let container=NSView(frame:.zero);container.translatesAutoresizingMaskIntoConstraints=false;content.addSubview(container)
        NSLayoutConstraint.activate([container.leadingAnchor.constraint(equalTo:content.leadingAnchor),container.trailingAnchor.constraint(equalTo:content.trailingAnchor),container.topAnchor.constraint(equalTo:content.topAnchor),container.bottomAnchor.constraint(equalTo:content.bottomAnchor)])
        let bar=NSView(frame:.zero);bar.translatesAutoresizingMaskIntoConstraints=false;container.addSubview(bar)
        let mark=NSImageView();mark.image=Bundle.main.resourceURL.map {$0.appendingPathComponent("engine/neptune-logo-square.png")}.flatMap {NSImage(contentsOf:$0)};mark.imageScaling = .scaleProportionallyUpOrDown;mark.translatesAutoresizingMaskIntoConstraints=false;bar.addSubview(mark)
        let label=NSTextField(labelWithString:"NEPTUNE  /  TRAINING");label.font = .systemFont(ofSize:13,weight:.bold);label.textColor=NSColor(srgbRed:0.34,green:0.82,blue:0.95,alpha:1);label.translatesAutoresizingMaskIntoConstraints=false;bar.addSubview(label)
        dashboardStatus.font = .systemFont(ofSize:11);dashboardStatus.textColor=NSColor(srgbRed:0.67,green:0.74,blue:0.83,alpha:1);dashboardStatus.translatesAutoresizingMaskIntoConstraints=false;dashboardStatus.lineBreakMode = .byTruncatingTail;dashboardStatus.setContentCompressionResistancePriority(.defaultLow,for:.horizontal);bar.addSubview(dashboardStatus)
        let controls=NSStackView();controls.orientation = .horizontal;controls.spacing=8;controls.translatesAutoresizingMaskIntoConstraints=false
        for button in [reviewButton!,folderButton!,connect!,run!] {button.removeFromSuperview();controls.addArrangedSubview(button)}
        bar.addSubview(controls)
        let scroll=NSScrollView(frame:.zero);scroll.translatesAutoresizingMaskIntoConstraints=false;scroll.hasVerticalScroller=true;scroll.drawsBackground=false;container.addSubview(scroll)
        let body=FlippedStackView(frame:.zero);body.orientation = .vertical;body.alignment = .leading;body.spacing=18;body.edgeInsets=NSEdgeInsets(top:22,left:22,bottom:22,right:22);body.translatesAutoresizingMaskIntoConstraints=false;scroll.documentView=body;dashboardBody=body
        NSLayoutConstraint.activate([
            bar.leadingAnchor.constraint(equalTo:container.leadingAnchor),bar.trailingAnchor.constraint(equalTo:container.trailingAnchor),bar.topAnchor.constraint(equalTo:container.topAnchor),bar.heightAnchor.constraint(equalToConstant:52),
            mark.leadingAnchor.constraint(equalTo:bar.leadingAnchor,constant:18),mark.centerYAnchor.constraint(equalTo:bar.centerYAnchor),mark.widthAnchor.constraint(equalToConstant:36),mark.heightAnchor.constraint(equalToConstant:36),
            label.leadingAnchor.constraint(equalTo:mark.trailingAnchor,constant:10),label.centerYAnchor.constraint(equalTo:bar.centerYAnchor),
            dashboardStatus.leadingAnchor.constraint(equalTo:label.trailingAnchor,constant:16),dashboardStatus.centerYAnchor.constraint(equalTo:bar.centerYAnchor),
            controls.trailingAnchor.constraint(equalTo:bar.trailingAnchor,constant:-18),controls.centerYAnchor.constraint(equalTo:bar.centerYAnchor),
            dashboardStatus.trailingAnchor.constraint(lessThanOrEqualTo:controls.leadingAnchor,constant:-16),
            scroll.leadingAnchor.constraint(equalTo:container.leadingAnchor),scroll.trailingAnchor.constraint(equalTo:container.trailingAnchor),scroll.topAnchor.constraint(equalTo:bar.bottomAnchor),scroll.bottomAnchor.constraint(equalTo:container.bottomAnchor),
            body.widthAnchor.constraint(equalTo:scroll.contentView.widthAnchor)
        ])
        dashboard=container
        // One window: this Mac's card, job and controls sit above Neptune's readouts; activity and version below.
        let logo=NSImageView();logo.image=Bundle.main.resourceURL.map {$0.appendingPathComponent("engine/neptune-logo-wide.png")}.flatMap {NSImage(contentsOf:$0)};logo.imageScaling = .scaleProportionallyUpOrDown
        logo.widthAnchor.constraint(equalToConstant:260).isActive=true;logo.heightAnchor.constraint(equalToConstant:60).isActive=true
        let views=helperContent.arrangedSubviews
        for view in views {helperContent.removeArrangedSubview(view);view.removeFromSuperview()}
        helperContent.removeFromSuperview()
        let controlRow=views.first {($0 as? NSStackView)?.arrangedSubviews.contains(device)==true}
        let footer=views.first {($0 as? NSStackView)?.arrangedSubviews.contains(version)==true}
        pinnedTop=[logo]+thisMacCards+[controlRow].compactMap {$0}
        pinnedBottom=[activityToggle!,activityScroll!,footer].compactMap {$0}
        for view in pinnedTop+pinnedBottom {dashboardBody.addArrangedSubview(view)}
        for view in thisMacCards+[activityScroll!] {view.widthAnchor.constraint(equalTo:dashboardBody.widthAnchor,constant:-44).isActive=true}
        renderDashboard(["computers":[],"queue":[]])
    }
    func resizeForState() {window?.contentView?.layoutSubtreeIfNeeded()}
    @objc func reloadDashboard() {
        guard !dashboardLoading,let data=cachedCredential,
              let config=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any],
              let token=config["token"] as? String,token.count==64,
              let site=config["site"] as? String,site=="https://neptunefrc.com",
              let url=URL(string:"https://neptunefrc.com/api/robot-detector.php") else {
            if cachedCredential == nil {dashboardStatus.stringValue="Connect this Mac to Neptune"}
            return
        }
        dashboardLoading=true
        var request=URLRequest(url:url);request.httpMethod="POST";request.timeoutInterval=15
        request.setValue("application/json",forHTTPHeaderField:"Content-Type")
        request.setValue("Bearer "+token,forHTTPHeaderField:"Authorization")
        request.httpBody=Data(#"{"action":"dashboard"}"#.utf8)
        URLSession.shared.dataTask(with:request) {data,response,error in
            let payload=data.flatMap {try? JSONSerialization.jsonObject(with:$0) as? [String:Any]}
            DispatchQueue.main.async {
                self.dashboardLoading=false
                if let response=response as? HTTPURLResponse,response.statusCode==200,let payload=payload,
                   payload["computers"] is [[String:Any]] {
                    self.dashboardStatus.stringValue="Live readouts · updated "+DateFormatter.localizedString(from:Date(),dateStyle:.none,timeStyle:.short)
                    self.renderDashboard(payload)
                } else {
                    self.dashboardStatus.stringValue="Readouts unavailable · Refresh to retry"
                }
            }
        }.resume()
    }
    @objc func toggleFullScreen() {window.toggleFullScreen(nil)}
    func dashText(_ string:String,_ size:CGFloat=12,_ color:NSColor = .white,_ weight:NSFont.Weight = .regular)->NSTextField {
        let field=NSTextField(labelWithString:string);field.font = .systemFont(ofSize:size,weight:weight);field.textColor=color
        field.lineBreakMode = .byTruncatingTail;field.maximumNumberOfLines=1
        field.toolTip=string
        return field
    }
    func dashCard(_ title:String,_ minimumHeight:CGFloat)->NSStackView {
        let panel=StatusCard(fill:NSColor(srgbRed:0.09,green:0.18,blue:0.30,alpha:0.92),outline:NSColor(srgbRed:0.22,green:0.36,blue:0.50,alpha:1))
        let stack=NSStackView();stack.orientation = .vertical;stack.alignment = .leading;stack.spacing=10;stack.translatesAutoresizingMaskIntoConstraints=false;panel.addSubview(stack)
        dashboardBody.addArrangedSubview(panel)
        NSLayoutConstraint.activate([stack.leadingAnchor.constraint(equalTo:panel.leadingAnchor,constant:14),stack.trailingAnchor.constraint(equalTo:panel.trailingAnchor,constant:-14),stack.topAnchor.constraint(equalTo:panel.topAnchor,constant:14),stack.bottomAnchor.constraint(equalTo:panel.bottomAnchor,constant:-14),panel.widthAnchor.constraint(equalTo:dashboardBody.widthAnchor,constant:-44),panel.heightAnchor.constraint(greaterThanOrEqualToConstant:minimumHeight)])
        stack.addArrangedSubview(dashText(title,14,NSColor(srgbRed:0.34,green:0.82,blue:0.95,alpha:1),.bold))
        return stack
    }
    func dashMeter(_ title:String,_ value:Double?,_ text:String)->HardwareMeter {
        let meter=HardwareMeter(title);meter.show(value,text)
        meter.heightAnchor.constraint(equalToConstant:31).isActive=true
        return meter
    }
    func renderDashboard(_ data:[String:Any]) {
        let pinned=Set((pinnedTop+pinnedBottom).map {ObjectIdentifier($0)})
        for view in dashboardBody.arrangedSubviews {dashboardBody.removeArrangedSubview(view);if !pinned.contains(ObjectIdentifier(view)) {view.removeFromSuperview()}}
        for view in pinnedTop {dashboardBody.addArrangedSubview(view)}
        defer {for view in pinnedBottom {dashboardBody.addArrangedSubview(view)};dashboardBody.layoutSubtreeIfNeeded()}
        let config=cachedCredential.flatMap {try? JSONSerialization.jsonObject(with:$0) as? [String:Any]}
        let selfID=config?["computer_id"] as? String
        let muted=NSColor(srgbRed:0.61,green:0.68,blue:0.77,alpha:1)
        let computers=data["computers"] as? [[String:Any]] ?? []
        let queue=data["queue"] as? [[String:Any]] ?? []
        let running=queue.filter {($0["state"] as? String)=="running"}
        let waiting=queue.filter {($0["state"] as? String)=="waiting"}
        var connected=cachedCredential != nil
#if DASHBOARD_PREVIEW
        connected=true
#endif
        if !connected {
            let card=dashCard("CONNECT THIS MAC",110)
            card.addArrangedSubview(dashText("Connect to Neptune and approve this Mac in your browser to see training readouts.",12,muted))
            let button=NSButton(title:"Connect to Neptune",target:self,action:#selector(reconnect));button.bezelStyle = .rounded;card.addArrangedSubview(button)
            return
        }
        let active=dashCard("RUNNING NOW  ·  \(running.count) active",running.isEmpty ? 90:290)
        if let job=running.first {
            active.addArrangedSubview(dashText(job["title"] as? String ?? "Training",16,.white,.bold))
            active.addArrangedSubview(dashText(job["message"] as? String ?? "",12,muted))
            if let id=job["computer_id"] as? String,let worker=computers.first(where:{($0["id"] as? String)==id}) {
                let counters=worker["counters"] as? [String:Any] ?? [:]
                let pass=(counters["pass"] as? NSNumber)?.intValue ?? 0
                let passes=(counters["passes"] as? NSNumber)?.intValue ?? 0
                let batch=(counters["batch"] as? NSNumber)?.intValue ?? 0
                let batches=(counters["batches"] as? NSNumber)?.intValue ?? 0
                if passes>0 {
                    active.addArrangedSubview(dashText("Stage · pass \(pass)/\(passes) · batch \(batch)/\(batches)",12,muted))
                    let batchPart=batches>0 ? Double(batch)/Double(batches) : 0
                    let fraction=(Double(pass-1)+batchPart)/Double(passes)
                    let bar=dashMeter("Progress",fraction,"\(Int(100*fraction))%")
                    active.addArrangedSubview(bar)
                }
                let lines=worker["log"] as? [[Any]] ?? []
                if !lines.isEmpty {
                    let log=NSTextView(frame:.zero);log.isEditable=false;log.isSelectable=true;log.drawsBackground=true
                    log.backgroundColor=NSColor(srgbRed:0.05,green:0.10,blue:0.18,alpha:1)
                    log.textColor=NSColor(srgbRed:0.44,green:0.74,blue:0.97,alpha:1)
                    log.font = .monospacedSystemFont(ofSize:11,weight:.regular)
                    log.string=lines.suffix(16).map { row in
                        let time=(row.first as? NSNumber).map {DateFormatter.localizedString(from:Date(timeIntervalSince1970:$0.doubleValue),dateStyle:.none,timeStyle:.short)} ?? ""
                        return time+"  "+(row.count>1 ? String(describing:row[1]) : "")
                    }.joined(separator:"\n")
                    let scroll=NSScrollView();scroll.documentView=log;scroll.hasVerticalScroller=true;scroll.drawsBackground=false
                    scroll.heightAnchor.constraint(equalToConstant:185).isActive=true;active.addArrangedSubview(scroll)
                }
            }
            if running.count>1 {active.addArrangedSubview(dashText("+ \(running.count-1) other active job(s)",11,muted))}
        } else {active.addArrangedSubview(dashText("No training job is running.",12,muted))}
        let others=computers.filter {selfID == nil || ($0["id"] as? String) != selfID}
        let helpers=dashCard("OTHER HELPERS  ·  \(others.filter{($0["online"] as? Bool)==true}.count) online",others.isEmpty ? 90:CGFloat(others.count)*185+40)
        if others.isEmpty {helpers.addArrangedSubview(dashText("No other computers connected.",12,muted))}
        for worker in others {
            let name=worker["name"] as? String ?? worker["device"] as? String ?? "Computer"
            let state=worker["job"] as? [String:Any]
            let status=state != nil ? "Training" : ((worker["online"] as? Bool ?? false) ? "Available":"Offline")
            helpers.addArrangedSubview(dashText(name+"   ·   "+status,14,.white,.semibold))
            let device=worker["device"] as? String ?? ""
            let platform=worker["platform"] as? String ?? ""
            let version=worker["version"] as? String ?? ""
            helpers.addArrangedSubview(dashText([platform,device,version].filter{!$0.isEmpty}.joined(separator:" · "),11,muted))
            let stats=worker["stats"] as? [String:Any] ?? [:]
            let gpu=stats["gpu"] as? [String:Any] ?? [:]
            let cpu=(stats["cpu"] as? NSNumber)?.doubleValue
            let gpuUse=(gpu["util"] as? NSNumber)?.doubleValue
            let ram=(stats["ram_used_mb"] as? NSNumber)?.doubleValue
            let ramTotal=(stats["ram_total_mb"] as? NSNumber)?.doubleValue
            let vram=(gpu["mem_used_mb"] as? NSNumber)?.doubleValue
            let vramTotal=(gpu["mem_total_mb"] as? NSNumber)?.doubleValue
            func memory(_ used:Double?,_ total:Double?)->String {
                guard let used=used else {return "—"}
                return total.map {String(format:"%.1f / %.1f GB",used/1024,$0/1024)} ?? String(format:"%.1f GB",used/1024)
            }
            let row1=NSStackView();row1.orientation = .horizontal;row1.distribution = .fillEqually;row1.spacing=20
            row1.addArrangedSubview(dashMeter("CPU",cpu.map{$0/100},cpu.map{String(format:"%.0f%%",$0)} ?? "—"))
            row1.addArrangedSubview(dashMeter("GPU",gpuUse.map{$0/100},gpuUse.map{String(format:"%.0f%%",$0)} ?? "—"))
            helpers.addArrangedSubview(row1)
            let row2=NSStackView();row2.orientation = .horizontal;row2.distribution = .fillEqually;row2.spacing=20
            row2.addArrangedSubview(dashMeter("RAM",(ram != nil && ramTotal != nil && ramTotal!>0) ? ram!/ramTotal!:nil,memory(ram,ramTotal)))
            row2.addArrangedSubview(dashMeter("GPU memory",(vram != nil && vramTotal != nil && vramTotal!>0) ? vram!/vramTotal!:nil,memory(vram,vramTotal)))
            helpers.addArrangedSubview(row2)
            helpers.addArrangedSubview(dashText(state?["message"] as? String ?? "No assigned job",11,muted))
            if worker["id"] as? String != others.last?["id"] as? String {
                let rule=NSBox();rule.boxType = .separator;helpers.addArrangedSubview(rule)
            }
        }
        let queueCard=dashCard("QUEUE  ·  \(waiting.count) waiting",CGFloat(max(90,60+waiting.count*25)))
        if waiting.isEmpty {queueCard.addArrangedSubview(dashText("No jobs waiting.",12,muted))}
        for item in waiting {queueCard.addArrangedSubview(dashText((item["title"] as? String ?? "Job")+" · "+(item["message"] as? String ?? "Waiting"),12,.white))}
    }
    func updateTelemetry(_ payload:[String:Any]) {
        let stats=payload["stats"] as? [String:Any] ?? [:],gpu=stats["gpu"] as? [String:Any] ?? [:],counters=payload["counters"] as? [String:Any] ?? [:]
        func number(_ data:[String:Any],_ key:String)->Double? {(data[key] as? NSNumber)?.doubleValue}
        let cpu=number(stats,"cpu"),gu=number(gpu,"util")
        cpuMeter.show(cpu.map {$0/100},cpu.map {String(format:"%.0f%%",$0)} ?? "—");gpuMeter.show(gu.map {$0/100},gu.map {String(format:"%.0f%%",$0)} ?? "—")
        func memory(_ meter:HardwareMeter,_ data:[String:Any],_ usedKey:String,_ totalKey:String) {
            guard let used=number(data,usedKey) else {meter.show(nil,"—");return}
            if let total=number(data,totalKey),total>0 {meter.show(used/total,String(format:"%.1f / %.1f GB",used/1024,total/1024))} else {meter.show(nil,String(format:"%.1f GB",used/1024))}
        }
        memory(ramMeter,stats,"ram_used_mb","ram_total_mb");memory(vramMeter,gpu,"mem_used_mb","mem_total_mb")
        computerDetail.stringValue="Mac · \(device.titleOfSelectedItem ?? "Automatic") · \(gpu["name"] as? String ?? "GPU unavailable")"
        if let pass=number(counters,"pass"),let passes=number(counters,"passes"),passes>0 {
            let batch=number(counters,"batch") ?? 0,batches=number(counters,"batches") ?? 0
            stageProgress.doubleValue=100*((pass-1)+(batches>0 ? batch/batches:0))/passes
            stageText.stringValue="Stage · pass \(Int(pass))/\(Int(passes)) · batch \(Int(batch))/\(Int(batches))"+(number(counters,"it_s").map {String(format:" · %.2f it/s",$0)} ?? "")
        } else if let match=number(counters,"match"),let matches=number(counters,"matches"),matches>0 {stageProgress.doubleValue=100*match/matches;stageText.stringValue="Stage · match \(Int(match))/\(Int(matches))"}
        else {stageText.stringValue=busy ? "Stage · waiting for counters":"No assigned job";stageProgress.doubleValue=0}
    }
    func append(_ message:String) {
        // Do not put credentials, callback codes, or raw protocol records into logs.
        let text=message.replacingOccurrences(of:"[a-f0-9]{64}",with:"[fingerprint omitted]",options:.regularExpression)
        let line=DateFormatter.localizedString(from:Date(),dateStyle:.none,timeStyle:.medium)+"  "+text+"\n"
        log.textStorage?.append(NSAttributedString(string:line,attributes:[.foregroundColor:NSColor.white,.font:NSFont.monospacedSystemFont(ofSize:12,weight:.regular)]));if log.string.count>100000 {log.textStorage?.deleteCharacters(in:NSRange(location:0,length:20000))};log.scrollToEndOfDocument(nil);try? logFile?.write(contentsOf:Data(line.utf8))
    }
    func send(_ value:[String:Any]) {if let data=try? JSONSerialization.data(withJSONObject:value) {try? input?.write(contentsOf:data+Data([10]))}}
    func launch(_ command:String) {
        guard task == nil else {return}
        guard let resources=Bundle.main.resourceURL else {return}
        var payload:[String:Any]=["command":command,"device":device.titleOfSelectedItem ?? "Automatic"]
        if command=="image_folder" {
            guard let folder=imageFolderPath else {return};folderReview=true;payload["folder"]=folder
        } else if command=="connect" {payload["site"]="https://neptunefrc.com"} else if command=="review" {
            reviewing=true
            if let data=cachedCredential,let config=try? JSONSerialization.jsonObject(with:data) as? [String:Any] {payload["connection"]=config}
        } else {
            guard let data=cachedCredential,let config=try? JSONSerialization.jsonObject(with:data) as? [String:Any] else {connection.stringValue="Disconnected";return};payload["connection"]=config
        }
        let process=Process();process.executableURL=resources.appendingPathComponent("python/bin/python3.13");process.arguments=["-I","-B",resources.appendingPathComponent("engine/native_bootstrap.py").path]
        let models=support.appendingPathComponent("robot-models");try? FileManager.default.createDirectory(at:models,withIntermediateDirectories:true,attributes:[.posixPermissions:0o700])
        var env=ProcessInfo.processInfo.environment
        for key in ["PYTHONPATH","PYTHONHOME","DYLD_LIBRARY_PATH","DYLD_INSERT_LIBRARIES"] {env.removeValue(forKey:key)}
        env["PATH"]=resources.appendingPathComponent("engine/vendor/bin").path+":/usr/bin:/bin:/usr/sbin:/sbin";env["NEPTUNE_ROBOT_MODELS"]=models.path;env["PYTHONDONTWRITEBYTECODE"]="1";env["NEPTUNE_HELPER_PIPELINE"]="facts";env["MPLCONFIGDIR"]=support.appendingPathComponent("matplotlib").path;process.environment=env
        let incoming=Pipe(),outgoing=Pipe();process.standardInput=incoming;process.standardOutput=outgoing
        process.standardError=logFile;input=incoming.fileHandleForWriting;buffer=Data();task=process
        outgoing.fileHandleForReading.readabilityHandler={handle in let data=handle.availableData;if data.isEmpty {handle.readabilityHandler=nil;return};DispatchQueue.main.async {self.buffer.append(data);while let end=self.buffer.firstIndex(of:10) {let row=self.buffer.prefix(upTo:end);self.buffer.removeSubrange(...end);if let event=(try? JSONSerialization.jsonObject(with:row)) as? [String:Any] {self.event(event)}}}}
        process.terminationHandler={_ in DispatchQueue.main.async {self.task=nil;self.input=nil;self.setBusy(false);if self.quitting {NSApp.terminate(nil)} else if let command=self.pendingCommand {self.pendingCommand=nil;self.launch(command)}}}
        do {try process.run();connection.stringValue=command=="connect" ? "Waiting for browser approval…":"Connecting…";send(payload)} catch {task=nil;append(error.localizedDescription);connection.stringValue="Unable to start"}
    }
    func event(_ value:[String:Any]) {
        switch value["event"] as? String {
        case "telemetry":
            if let payload=value["payload"] as? [String:Any] {updateTelemetry(payload)}
        case "image_folder_url":
            if let text=value["url"] as? String,let url=URL(string:text),url.scheme=="http",url.host=="127.0.0.1" {NSWorkspace.shared.open(url);connection.stringValue="Local image labeling";status.stringValue="Correct bumper boxes in the image labeler. Only checked frames enter the local YOLO export.";folderButton.title="Close image labeler";reviewButton.isEnabled=false;stop.isEnabled=false}
        case "review_url":
            if let text=value["url"] as? String,let url=URL(string:text),url.scheme=="http",url.host=="127.0.0.1" {NSWorkspace.shared.open(url);connection.stringValue="Local robot tracking review";status.stringValue="Choose a tagged match in the review window. Close review here to reconnect for training.";reviewButton.title="Close tracking review";stop.isEnabled=false}
        case "credential":
            if let config=value["connection"] as? [String:Any],let data=try? JSONSerialization.data(withJSONObject:config) {do {try saveCredential(data);cachedCredential=data;append("Connection saved in Keychain. This Mac will reconnect after updates.");DispatchQueue.main.asyncAfter(deadline:.now()+1) {self.launch("run")}} catch {append(error.localizedDescription)}}
        case "connection":
            if value["connected"] as? Bool == false {connection.stringValue="Reconnecting to Neptune…";dashboardStatus.stringValue="Reconnecting…";availability.stringValue="Offline";return}
            let config=cachedCredential.flatMap {try? JSONSerialization.jsonObject(with:$0) as? [String:Any]}
            let shortID=(config?["computer_id"] as? String).map {String($0.prefix(4)).uppercased()}
            connection.stringValue="Connected to Neptune"+(shortID.map {" · "+$0} ?? "");dashboardStatus.stringValue="Connected"+(shortID.map {" · "+$0} ?? "");availability.stringValue=busy ? "Working":"Available"
        case "busy":setBusy(value["value"] as? Bool ?? false);if !(value["value"] as? Bool ?? false) {progress.doubleValue=0;remaining.stringValue="No job running"}
        case "error":status.stringValue=value["message"] as? String ?? "Needs attention";connection.stringValue="Needs attention — your saved work is kept";append(status.stringValue)
        case "status":
            let message=value["message"] as? String ?? "";append(message)
            // "Progress: 37% · about 42 min left" drives the bar; the rest stays as the status text.
            let lines=message.components(separatedBy:"\n")
            if let line=lines.first(where:{$0.hasPrefix("Progress: ")}) {
                let rest=String(line.dropFirst("Progress: ".count))
                if let pct=Double(rest.prefix(while:{$0.isNumber})) {progress.doubleValue=pct;remaining.stringValue=rest}
            }
            if busy {
                jobTitle.stringValue=lines.first ?? "RUNNING NOW";jobTitle.toolTip=jobTitle.stringValue
                status.stringValue=lines.first(where:{$0.hasPrefix("Now:")}) ?? lines.filter {!$0.hasPrefix("Progress: ")}.joined(separator:"\n")
                nextStatus.stringValue=lines.first(where:{$0.hasPrefix("Next:")}) ?? "";nextStatus.toolTip=nextStatus.stringValue
            } else {status.stringValue="No assigned job"}
        default:break
        }
    }
    func setBusy(_ value:Bool) {
        busy=value;dashboardStatus.stringValue=value ? "Training on this Mac":"Mac available";availability.stringValue=value ? "Working":"Available";folderButton.isEnabled = !value;reviewButton.isEnabled = !value && !folderReview;stop.isEnabled=value;connect.isEnabled = !value;device.isEnabled = !value
        jobCardHeight?.constant=value ? 154:62;statusHeight?.constant=value ? 28:18
        stageRow.isHidden = !value;progressRow.isHidden = !value;nextStatus.isHidden = !value
        if !value {jobTitle.stringValue="THIS MAC";status.stringValue="No assigned job"}
        resizeForState()
        if !value,let handler=installHandler {installHandler=nil;send(["command":"quit"]);handler()}
    }
    @objc func toggleActivity() {activityScroll.isHidden.toggle();activityToggle.title=activityScroll.isHidden ? "Show activity":"Hide activity";resizeForState()}
    @objc func reviewTracking() {
        guard !busy else {return}
        if reviewing {reviewing=false;reviewButton.title="Review robot tracking…";pendingCommand="run";send(["command":"quit"]);return}
        if task != nil {pendingCommand="review";send(["command":"quit"])} else {launch("review")}
    }
    @objc func labelImageFolder() {
        guard !busy else {return}
        if folderReview {folderReview=false;folderButton.title="Label image folder…";if task != nil {pendingCommand="run";send(["command":"quit"])} else {launch("run")};return}
        let picker=NSOpenPanel();picker.title="Choose close-up robot images";picker.message="Neptune suggests bumper boxes. Review and save labels in a separate local export; your originals stay unchanged.";picker.canChooseDirectories=true;picker.canChooseFiles=false;picker.allowsMultipleSelection=false
        if picker.runModal() == .OK,let url=picker.url {imageFolderPath=url.path;reviewing=false;reviewButton.title="Review tracking…";if task != nil {pendingCommand="image_folder";send(["command":"quit"])} else {launch("image_folder")}}
    }
    @objc func stopMatch() {send(["command":"stop"]);append("Finishing this match, then saving progress.")}
    @objc func reconnect() {
        guard !busy else {return}
        // An explicit reconnect must replace a revoked credential through owner approval.
        // Keep the old Keychain item until the new connection has been approved and saved.
        if task != nil {pendingCommand="connect";send(["command":"quit"])} else {launch("connect")}
    }
    @objc func changeDevice() {UserDefaults.standard.set(device.titleOfSelectedItem,forKey:"device");if !busy {pendingCommand="run";send(["command":"quit"]);if task == nil {pendingCommand=nil;launch("run")}}}
    @objc func openSite() {NSWorkspace.shared.open(URL(string:"https://neptunefrc.com/admin/community-learning.php")!)}
    @objc func showLogs() {NSWorkspace.shared.open(FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/Neptune Training Helper"))}
    @objc func checkUpdates() {updater.checkForUpdates(nil)}
    @objc func importConnection() {
        guard !busy else {return};let picker=NSOpenPanel();picker.title="Choose trainer-connection.json from your existing helper";picker.canChooseDirectories=false
        if picker.runModal() == .OK,let url=picker.url {do {
            let data=try Data(contentsOf:url);guard data.count<4096,let config=try JSONSerialization.jsonObject(with:data) as? [String:Any],let site=config["site"] as? String,site=="https://neptunefrc.com",let token=config["token"] as? String,token.range(of:"^[a-f0-9]{64}$",options:.regularExpression) != nil else {throw NSError(domain:"Neptune",code:1,userInfo:[NSLocalizedDescriptionKey:"Choose a valid Neptune trainer connection."])}
            try saveCredential(data);cachedCredential=data
            // Private weights remain local; no credentials or weights enter the application bundle.
            let source=url.deletingLastPathComponent().appendingPathComponent("robot-models"),dest=support.appendingPathComponent("robot-models")
            for name in ["manifest.json","best_bumper_model.pt","coco_model.pt"] {let from=source.appendingPathComponent(name),to=dest.appendingPathComponent(name);if FileManager.default.fileExists(atPath:from.path) && !FileManager.default.fileExists(atPath:to.path) {try FileManager.default.createDirectory(at:dest,withIntermediateDirectories:true,attributes:[.posixPermissions:0o700]);try FileManager.default.copyItem(at:from,to:to)}}
            append("Existing connection imported to Keychain. Training files stay in place.");if task != nil {pendingCommand="run";send(["command":"quit"])} else {launch("run")}
        } catch {append(error.localizedDescription)}}
    }
    func updater(_ updater:SPUUpdater,didFindValidUpdate item:SUAppcastItem) {updateStatus.stringValue="Update \(item.displayVersionString) is available. Install using the update window."}
    func updater(_ updater:SPUUpdater,didAbortWithError error:Error) {updateStatus.stringValue="Update check: "+error.localizedDescription}
    func updater(_ updater:SPUUpdater,shouldPostponeRelaunchForUpdate item:SUAppcastItem,untilInvokingBlock handler:@escaping ()->Void)->Bool {if busy {installHandler=handler;stopMatch();updateStatus.stringValue="Update ready. Finishing this match before restarting.";return true};send(["command":"quit"]);return false}
    func applicationShouldTerminate(_ sender:NSApplication)->NSApplication.TerminateReply {
        if busy {let alert=NSAlert();alert.messageText="Finish this match and quit?";alert.informativeText="Progress will be saved before this app closes.";alert.addButton(withTitle:"Finish and quit");alert.addButton(withTitle:"Keep running");if alert.runModal() != .alertFirstButtonReturn {return .terminateCancel};quitting=true;send(["command":"quit"]);return .terminateCancel}
        send(["command":"quit"]);return .terminateNow
    }
    func windowShouldClose(_ sender:NSWindow)->Bool {NSApp.terminate(nil);return false}
    func applicationShouldHandleReopen(_ sender:NSApplication,hasVisibleWindows flag:Bool)->Bool {window.makeKeyAndOrderFront(nil);return true}
}
