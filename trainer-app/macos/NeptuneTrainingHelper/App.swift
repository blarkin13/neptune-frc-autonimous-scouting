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

@main @MainActor final class App: NSObject, NSApplicationDelegate, NSWindowDelegate, SPUUpdaterDelegate {
    var window:NSWindow!;var updater:SPUStandardUpdaterController!
    var task:Process?;var input:FileHandle?;var buffer=Data();var busy=false;var quitting=false
    var cachedCredential:Data?;var pendingCommand:String?;var installHandler:(()->Void)?;var logFile:FileHandle?
    var status=NSTextField(wrappingLabelWithString:"Connect this Mac to Neptune to begin.")
    var connection=NSTextField(wrappingLabelWithString:"Disconnected")
    var updateStatus=NSTextField(wrappingLabelWithString:"Updates are checked automatically.")
    var version=NSTextField(wrappingLabelWithString:"")
    var reviewButton:NSButton!;var reviewing=false
    var progress=NSProgressIndicator();var remaining=NSTextField(labelWithString:"");var progressRow=NSStackView()
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
        updater=SPUStandardUpdaterController(startingUpdater:true,updaterDelegate:self,userDriverDelegate:nil)
        DispatchQueue.main.asyncAfter(deadline:.now()+2) {self.updater.updater.checkForUpdatesInBackground()}
        connection.stringValue="Checking saved Neptune connection…"
        status.stringValue="If macOS asks for Keychain access, use your Mac login password to let this app read its saved Neptune connection."
        DispatchQueue.global().async {let saved=loadCredential();DispatchQueue.main.async {self.cachedCredential=saved;if saved != nil {self.launch("run")} else {self.connection.stringValue="Disconnected";self.status.stringValue="Connect this Mac to Neptune to begin.";self.append("1. Connect to Neptune. 2. Approve this Mac in your browser. 3. Choose training or a match test on Neptune.")}}}
    }
    func buildUI() {
        let ink=NSColor(srgbRed:0.027,green:0.082,blue:0.133,alpha:1)
        let panel=NSColor(srgbRed:0.063,green:0.141,blue:0.216,alpha:1)
        let line=NSColor(srgbRed:0.16,green:0.275,blue:0.365,alpha:1)
        let accent=NSColor(srgbRed:0.325,green:0.831,blue:0.929,alpha:1)
        let muted=NSColor(srgbRed:0.66,green:0.74,blue:0.81,alpha:1)
        window=NSWindow(contentRect:NSRect(x:0,y:0,width:600,height:640),styleMask:[.titled,.closable,.miniaturizable],backing:.buffered,defer:false)
        window.appearance=NSAppearance(named:.darkAqua);window.title="Neptune Training Helper"
        window.minSize=NSSize(width:600,height:640);window.maxSize=NSSize(width:600,height:640)
        window.collectionBehavior=[.fullScreenNone];window.delegate=self
        window.backgroundColor=ink
        let root=NSStackView()
        root.orientation = .vertical;root.alignment = .leading;root.spacing=13
        root.edgeInsets=NSEdgeInsets(top:20,left:24,bottom:20,right:24)
        root.translatesAutoresizingMaskIntoConstraints=false
        window.contentView!.addSubview(root)
        NSLayoutConstraint.activate([root.leadingAnchor.constraint(equalTo:window.contentView!.leadingAnchor),root.trailingAnchor.constraint(equalTo:window.contentView!.trailingAnchor),root.topAnchor.constraint(equalTo:window.contentView!.topAnchor),root.bottomAnchor.constraint(equalTo:window.contentView!.bottomAnchor)])
        let engineIdentityURL=Bundle.main.url(forResource:"engine-identity",withExtension:"json")
        let engineIdentity=engineIdentityURL.flatMap {try? Data(contentsOf:$0)}.flatMap {try? JSONSerialization.jsonObject(with:$0) as? [String:Any]}
        let engineVersion=engineIdentity?["version"] as? String ?? "Unknown"
        version.stringValue="Version \(Bundle.main.object(forInfoDictionaryKey:"CFBundleShortVersionString") ?? "") · Engine \(engineVersion.components(separatedBy:"-").first ?? engineVersion)"
        version.textColor=muted;version.font = .systemFont(ofSize:11)
        let header=NSStackView();header.orientation = .horizontal;header.alignment = .centerY;header.spacing=14
        if let url=Bundle.main.url(forResource:"Icon",withExtension:"png"),let image=NSImage(contentsOf:url) {
            let mark=NSImageView(image:image);mark.imageScaling = .scaleProportionallyUpOrDown
            mark.widthAnchor.constraint(equalToConstant:62).isActive=true
            mark.heightAnchor.constraint(equalToConstant:62).isActive=true
            header.addArrangedSubview(mark)
        }
        let headerCopy=NSStackView();headerCopy.orientation = .vertical;headerCopy.alignment = .leading;headerCopy.spacing=2
        let eyebrow=NSTextField(labelWithString:"NEPTUNE  /  TRAINING")
        eyebrow.textColor=accent;eyebrow.font = .systemFont(ofSize:10,weight:.bold)
        let title=NSTextField(labelWithString:"Training Helper")
        title.textColor = .white;title.font = .systemFont(ofSize:22,weight:.bold)
        headerCopy.addArrangedSubview(eyebrow);headerCopy.addArrangedSubview(title);headerCopy.addArrangedSubview(version)
        header.addArrangedSubview(headerCopy);root.addArrangedSubview(header)
        header.widthAnchor.constraint(equalToConstant:552).isActive=true
        let card=NSView();card.wantsLayer=true;card.layer?.backgroundColor=panel.cgColor
        card.layer?.borderColor=line.cgColor;card.layer?.borderWidth=1;card.layer?.cornerRadius=12
        let cardStack=NSStackView();cardStack.orientation = .vertical;cardStack.alignment = .leading;cardStack.spacing=7
        cardStack.translatesAutoresizingMaskIntoConstraints=false;card.addSubview(cardStack)
        NSLayoutConstraint.activate([cardStack.leadingAnchor.constraint(equalTo:card.leadingAnchor,constant:16),cardStack.trailingAnchor.constraint(equalTo:card.trailingAnchor,constant:-16),cardStack.topAnchor.constraint(equalTo:card.topAnchor,constant:15),cardStack.bottomAnchor.constraint(equalTo:card.bottomAnchor,constant:-15)])
        let cardLabel=NSTextField(labelWithString:"CONNECTION")
        cardLabel.textColor=accent;cardLabel.font = .systemFont(ofSize:10,weight:.bold)
        cardStack.addArrangedSubview(cardLabel)
        connection.textColor = .white;connection.font = .systemFont(ofSize:17,weight:.semibold)
        status.textColor=muted;status.font = .systemFont(ofSize:13)
        for field in [connection,status] {
            field.lineBreakMode = .byWordWrapping;field.maximumNumberOfLines=4
            if field === status {field.heightAnchor.constraint(equalToConstant:72).isActive=true}   // room for four lines, always
            field.preferredMaxLayoutWidth=510;field.widthAnchor.constraint(equalToConstant:510).isActive=true
            cardStack.addArrangedSubview(field)
        }
        root.addArrangedSubview(card);card.widthAnchor.constraint(equalToConstant:552).isActive=true
        // % complete and time left for the job in progress, under the connection card (hidden while idle).
        progress.isIndeterminate=false;progress.minValue=0;progress.maxValue=100;progress.style = .bar
        progress.widthAnchor.constraint(equalToConstant:552).isActive=true
        remaining.textColor=accent;remaining.font = .systemFont(ofSize:13,weight:.semibold)
        progressRow.orientation = .vertical;progressRow.alignment = .leading;progressRow.spacing=4
        progressRow.addArrangedSubview(progress);progressRow.addArrangedSubview(remaining);remaining.stringValue="No job running"   // always shown, so nothing shifts
        root.addArrangedSubview(progressRow)
        let buttons=NSStackView();buttons.orientation = .horizontal;buttons.spacing=9
        run=NSButton(title:"Open Neptune",target:self,action:#selector(openSite))
        connect=NSButton(title:"Reconnect",target:self,action:#selector(reconnect))
        reviewButton=NSButton(title:"Review tracking…",target:self,action:#selector(reviewTracking))
        for button in [run!,connect!,reviewButton!] {
            button.bezelStyle = .rounded;button.font = .systemFont(ofSize:12,weight:.medium)
            button.heightAnchor.constraint(equalToConstant:34).isActive=true
            buttons.addArrangedSubview(button)
        }
        run.contentTintColor=accent;root.addArrangedSubview(buttons)
        let controls=NSStackView();controls.orientation = .horizontal;controls.spacing=12
        let deviceLabel=NSTextField(labelWithString:"Training device")
        deviceLabel.textColor=muted;deviceLabel.font = .systemFont(ofSize:12)
        controls.addArrangedSubview(deviceLabel)
        device.addItems(withTitles:["Automatic","Mac GPU","CPU"])
        device.selectItem(withTitle:UserDefaults.standard.string(forKey:"device") ?? "Automatic")
        device.target=self;device.action=#selector(changeDevice);controls.addArrangedSubview(device)
        stop=NSButton(title:"Stop after this match",target:self,action:#selector(stopMatch))
        stop.isEnabled=false;controls.addArrangedSubview(stop);root.addArrangedSubview(controls)
        updateStatus.textColor=muted;updateStatus.font = .systemFont(ofSize:11)
        updateStatus.lineBreakMode = .byWordWrapping;updateStatus.maximumNumberOfLines=2
        updateStatus.widthAnchor.constraint(equalToConstant:552).isActive=true
        root.addArrangedSubview(updateStatus)
        // The activity log stays hidden until asked for.
        activityToggle=NSButton(title:"Show activity",target:self,action:#selector(toggleActivity))
        activityToggle.bezelStyle = .rounded;activityToggle.font = .systemFont(ofSize:12,weight:.medium)
        root.addArrangedSubview(activityToggle)
        let scroll=NSScrollView();scroll.hasVerticalScroller=true;scroll.borderType = .noBorder
        scroll.wantsLayer=true;scroll.layer?.backgroundColor=NSColor(srgbRed:0.027,green:0.067,blue:0.11,alpha:1).cgColor
        scroll.layer?.borderColor=line.cgColor;scroll.layer?.borderWidth=1;scroll.layer?.cornerRadius=10
        scroll.documentView=log;log.isEditable=false;log.isSelectable=true
        log.font = .monospacedSystemFont(ofSize:11,weight:.regular);log.textColor = .white
        log.backgroundColor=NSColor(srgbRed:0.027,green:0.067,blue:0.11,alpha:1)
        log.autoresizingMask=[.width];log.isVerticallyResizable=true;log.textContainer?.widthTracksTextView=true
        root.addArrangedSubview(scroll);scroll.widthAnchor.constraint(equalToConstant:552).isActive=true;activityScroll=scroll;scroll.isHidden=true
        scroll.heightAnchor.constraint(greaterThanOrEqualToConstant:190).isActive=true
        let menu=NSMenu();let item=NSMenuItem();let appMenu=NSMenu()
        appMenu.addItem(withTitle:"Check for Updates…",action:#selector(checkUpdates),keyEquivalent:"")
        appMenu.addItem(withTitle:"Import existing helper connection…",action:#selector(importConnection),keyEquivalent:"")
        appMenu.addItem(withTitle:"Show logs",action:#selector(showLogs),keyEquivalent:"")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle:"Quit Neptune Training Helper",action:#selector(NSApplication.terminate(_:)),keyEquivalent:"q")
        item.submenu=appMenu;menu.addItem(item);NSApp.mainMenu=menu
        window.contentView!.layoutSubtreeIfNeeded();window.setContentSize(NSSize(width:600,height:640))   // one size: content never resizes the window
        window.center();window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)
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
        if command=="connect" {payload["site"]="https://neptunefrc.com"} else if command=="review" {
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
        case "review_url":
            if let text=value["url"] as? String,let url=URL(string:text),url.scheme=="http",url.host=="127.0.0.1" {NSWorkspace.shared.open(url);connection.stringValue="Local robot tracking review";status.stringValue="Choose a tagged match in the review window. Close review here to reconnect for training.";reviewButton.title="Close tracking review";stop.isEnabled=false}
        case "credential":
            if let config=value["connection"] as? [String:Any],let data=try? JSONSerialization.data(withJSONObject:config) {do {try saveCredential(data);cachedCredential=data;append("Connection saved in Keychain. This Mac will reconnect after updates.");DispatchQueue.main.asyncAfter(deadline:.now()+1) {self.launch("run")}} catch {append(error.localizedDescription)}}
        case "connection":
            if value["connected"] as? Bool == false {connection.stringValue="Reconnecting to Neptune…";return}
            let config=cachedCredential.flatMap {try? JSONSerialization.jsonObject(with:$0) as? [String:Any]}
            let shortID=(config?["computer_id"] as? String).map {String($0.prefix(4)).uppercased()}
            connection.stringValue="Connected to Neptune"+(shortID.map {" · "+$0} ?? "")
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
            status.stringValue=lines.filter {!$0.hasPrefix("Progress: ")}.joined(separator:"\n")
        default:break
        }
    }
    func setBusy(_ value:Bool) {busy=value;reviewButton.isEnabled = !value;stop.isEnabled=value;connect.isEnabled = !value;device.isEnabled = !value;if !value, let handler=installHandler {installHandler=nil;send(["command":"quit"]);handler()}}
    @objc func toggleActivity() {
        activityScroll.isHidden.toggle();activityToggle.title=activityScroll.isHidden ? "Show activity":"Hide activity"
    }
    @objc func reviewTracking() {
        guard !busy else {return}
        if reviewing {reviewing=false;reviewButton.title="Review robot tracking…";pendingCommand="run";send(["command":"quit"]);return}
        if task != nil {pendingCommand="review";send(["command":"quit"])} else {launch("review")}
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
