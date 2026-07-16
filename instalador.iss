#define AppName "Gerenciador de Fotos de Pessoal"
#define AppVersion "1.0.0"
#define AppExeName "GerenciadorFotos.exe"
#define AppPublisher "ComSoc"

[Setup]
; Este AppId deve permanecer o mesmo nas próximas versões para permitir atualizações.
AppId={{4658D6F9-D81F-477A-9EEE-D3D9C5D17E56}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Gerenciador de Fotos de Pessoal
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=build\installer-windows
OutputBaseFilename=Instalador-GerenciadorFotos-{#AppVersion}
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na Área de Trabalho"; GroupDescription: "Ícones adicionais:"; Flags: unchecked

[Files]
; Execute script_nuitka.py antes de compilar este instalador.
Source: "build\nuitka-windows\main.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Executar {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
var
  FullCleanupRequested: Boolean;

function ConfirmFullUninstall(): Boolean;
var
  Form: TForm;
  PromptLabel: TLabel;
  CleanupCheckBox: TCheckBox;
  OkButton, CancelButton: TNewButton;
begin
  Form := TForm.Create(nil);
  try
    Form.ClientWidth := ScaleX(440);
    Form.ClientHeight := ScaleY(160);
    Form.Caption := 'Desinstalar {#AppName}';
    Form.Position := poScreenCenter;

    PromptLabel := TLabel.Create(Form);
    PromptLabel.Parent := Form;
    PromptLabel.Left := ScaleX(20);
    PromptLabel.Top := ScaleY(20);
    PromptLabel.Width := Form.ClientWidth - ScaleX(40);
    PromptLabel.Height := ScaleY(40);
    PromptLabel.AutoSize := False;
    PromptLabel.WordWrap := True;
    PromptLabel.Caption := 'Deseja desinstalar o {#AppName} e todos os seus componentes?';
    PromptLabel.Font.Style := [fsBold];

    CleanupCheckBox := TCheckBox.Create(Form);
    CleanupCheckBox.Parent := Form;
    CleanupCheckBox.Left := ScaleX(20);
    CleanupCheckBox.Top := PromptLabel.Top + PromptLabel.Height + ScaleY(5);
    CleanupCheckBox.Width := Form.ClientWidth - ScaleX(40);
    CleanupCheckBox.Caption := 'Remover também configurações e miniaturas em cache';
    CleanupCheckBox.Checked := False;

    OkButton := TNewButton.Create(Form);
    OkButton.Parent := Form;
    OkButton.Width := ScaleX(80);
    OkButton.Caption := 'Sim';
    OkButton.ModalResult := mrYes;
    OkButton.Top := Form.ClientHeight - OkButton.Height - ScaleY(15);
    OkButton.Left := Form.ClientWidth - (OkButton.Width * 2) - ScaleX(25);

    CancelButton := TNewButton.Create(Form);
    CancelButton.Parent := Form;
    CancelButton.Width := ScaleX(80);
    CancelButton.Caption := 'Não';
    CancelButton.ModalResult := mrNo;
    CancelButton.Top := OkButton.Top;
    CancelButton.Left := Form.ClientWidth - CancelButton.Width - ScaleX(15);
    CancelButton.Default := True;

    if Form.ShowModal() = mrYes then
    begin
      FullCleanupRequested := CleanupCheckBox.Checked;
      Result := True;
    end
    else
      Result := False;
  finally
    Form.Free;
  end;
end;

function InitializeUninstall(): Boolean;
begin
  FullCleanupRequested := False;
  if UninstallSilent then
    Result := True
  else
    Result := ConfirmFullUninstall();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and FullCleanupRequested then
  begin
    // QStandardPaths: configuração, cache e QSettings utilizados pelo aplicativo.
    DelTree(ExpandConstant('{userappdata}\ComSoc\{#AppName}'), True, True, True);
    DelTree(ExpandConstant('{localappdata}\ComSoc\{#AppName}'), True, True, True);
    RegDeleteKeyIncludingSubkeys(HKCU, 'Software\ComSoc\{#AppName}');
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpPreparing) and WizardForm.PreparingNoRadio.Checked then
  begin
    MsgBox(
      'A instalação foi cancelada para proteger o trabalho em andamento.' + #13#10 +
      'Feche o aplicativo e tente novamente.',
      mbInformation,
      MB_OK
    );
    Result := False;
    WizardForm.Close;
  end;
end;
