# Interop Surface Dump

Generated from the installed RADAN interop assembly on this machine:

- `C:\Program Files\Mazak\Mazak\bin\Radan.Shared.Radraft.Interop.dll`

This file lists every exported interface name plus its methods, properties, and parameter lists where available.

## Exported Interfaces

- `Radan.Shared.Radraft.Interop.ICalculateCycleTimeResult`
- `Radan.Shared.Radraft.Interop.ICanDetectClosedGeometry`
- `Radan.Shared.Radraft.Interop.IDrawingEditor`
- `Radan.Shared.Radraft.Interop.IEntityInfo`
- `Radan.Shared.Radraft.Interop.IModelPro`
- `Radan.Shared.Radraft.Interop.INestProject`
- `Radan.Shared.Radraft.Interop.IPartEditor`
- `Radan.Shared.Radraft.Interop.IRadanAttribute`
- `Radan.Shared.Radraft.Interop.IRadanMacro`
- `Radan.Shared.Radraft.Interop.IRadanPartAttribute`
- `Radan.Shared.Radraft.Interop.IRadraftApplication`
- `Radan.Shared.Radraft.Interop.IRadraftApplicationFactory`
- `Radan.Shared.Radraft.Interop.ISheetUtilisationResult`
- `Radan.Shared.Radraft.Interop.IUnfoldOptions`
- `Radan.Shared.Radraft.Interop.IUnfoldResult`
- `Radraft.Interop.Application`
- `Radraft.Interop.ApplicationEvents`
- `Radraft.Interop.ApplicationEvents_Event`
- `Radraft.Interop.Document`
- `Radraft.Interop.IApplication`
- `Radraft.Interop.IDocument`
- `Radraft.Interop.IMac`
- `Radraft.Interop.IMacArgument`
- `Radraft.Interop.IMacArguments`
- `Radraft.Interop.IMacCommand`
- `Radraft.Interop.IMacCommands`
- `Radraft.Interop.IMacFile`
- `Radraft.Interop.IMacFiles`
- `Radraft.Interop.ISystemDataFile`
- `Radraft.Interop.ISystemDataFiles`
- `Radraft.Interop.ISystemDataItem`
- `Radraft.Interop.Mac`
- `Radraft.Interop.MacArgument`
- `Radraft.Interop.MacArguments`
- `Radraft.Interop.MacCommand`
- `Radraft.Interop.MacCommands`
- `Radraft.Interop.MacFile`
- `Radraft.Interop.MacFiles`
- `Radraft.Interop.SystemDataFile`
- `Radraft.Interop.SystemDataFiles`
- `Radraft.Interop.SystemDataItem`

## Radan.Shared.Radraft.Interop.ICalculateCycleTimeResult

Properties: 5

- `Int32 AutoToolErrorStatus` [get/set]
- `Double CycleTime` [get/set]
- `String Error` [get/set]
- `Boolean GeometryIsClosed` [get/set]
- `Boolean Success` [get/set]

Methods: 10

- `Int32 get_AutoToolErrorStatus()`
- `Double get_CycleTime()`
- `String get_Error()`
- `Boolean get_GeometryIsClosed()`
- `Boolean get_Success()`
- `Void set_AutoToolErrorStatus(Int32 value)`
- `Void set_CycleTime(Double value)`
- `Void set_Error(String value)`
- `Void set_GeometryIsClosed(Boolean value)`
- `Void set_Success(Boolean value)`

## Radan.Shared.Radraft.Interop.ICanDetectClosedGeometry

Properties: 0

- none

Methods: 1

- `Boolean PatternGeometryIsClosed(String pattern)`

## Radan.Shared.Radraft.Interop.IDrawingEditor

Properties: 14

- `Boolean IsOpen` [get]
- `String MFL_U_DEV_NAME_SPEC` [get/set]
- `Boolean MFL_U_PART_EDITOR_SPEC` [get/set]
- `Boolean MFL_U_SMOOTHING` [get/set]
- `Double ND_BOXMAXX1` [get]
- `Double ND_BOXMAXY1` [get]
- `Double ND_BOXMAXZ1` [get]
- `Double ND_BOXMINX1` [get]
- `Double ND_BOXMINY1` [get]
- `Double ND_BOXMINZ1` [get]
- `String ND_MATERIAL1` [get]
- `String ND_NAME1` [get]
- `Boolean ND_VIS1` [get]
- `Double ND_VOLUME1` [get]

Methods: 26

- `Boolean DeletePattern(String patternPath)`
- `Boolean get_IsOpen()`
- `String get_MFL_U_DEV_NAME_SPEC()`
- `Boolean get_MFL_U_PART_EDITOR_SPEC()`
- `Boolean get_MFL_U_SMOOTHING()`
- `Double get_ND_BOXMAXX1()`
- `Double get_ND_BOXMAXY1()`
- `Double get_ND_BOXMAXZ1()`
- `Double get_ND_BOXMINX1()`
- `Double get_ND_BOXMINY1()`
- `Double get_ND_BOXMINZ1()`
- `String get_ND_MATERIAL1()`
- `String get_ND_NAME1()`
- `Boolean get_ND_VIS1()`
- `Double get_ND_VOLUME1()`
- `Boolean mfl_auto_unfold(String ident)`
- `Double mfl_calculate_thickness(String ident)`
- `String mfl_info_scan_next()`
- `Boolean mfl_info_scan_start()`
- `Boolean mfl_object_info(String ident, Boolean massPropertiesRequired)`
- `Boolean mfl_read_model(String fileformat, Boolean heal, Boolean regularise, Boolean reverse, Boolean combine, Boolean allowComplexGeom, Double scale, Double thickness, String material, String filename)`
- `Boolean mfl_read_model_default(String fileformat, String filename, String material, Double thickness, Double scale)`
- `Void Open(String filename, Boolean discardChanges, String optionsFilePath)`
- `Void set_MFL_U_DEV_NAME_SPEC(String value)`
- `Void set_MFL_U_PART_EDITOR_SPEC(Boolean value)`
- `Void set_MFL_U_SMOOTHING(Boolean value)`

## Radan.Shared.Radraft.Interop.IEntityInfo

Properties: 30

- `Double BoxMaxX` [get]
- `Double BoxMaxY` [get]
- `Double BoxMaxZ` [get]
- `Double BoxMinX` [get]
- `Double BoxMinY` [get]
- `Double BoxMinZ` [get]
- `Double CentreOfGravityX` [get]
- `Double CentreOfGravityY` [get]
- `Double CentreOfGravityZ` [get]
- `Double ColourBlue` [get]
- `Double ColourGreen` [get]
- `Double ColourRed` [get]
- `Double Density` [get]
- `DensityUnit DensityUnits` [get]
- `DimensionUnit DimensionUnits` [get]
- `String Identifier` [get]
- `Double Mass` [get]
- `WeightUnit MassUnits` [get]
- `String Material` [get]
- `EntityMaterialStatus MaterialStatus` [get]
- `String Name` [get]
- `Int32 ScanLevel` [get]
- `Double SurfaceArea` [get]
- `AreaUnit SurfaceAreaUnits` [get]
- `Double Thickness` [get]
- `EntityThicknessStatus ThicknessStatus` [get]
- `ThicknessUnit ThicknessUnits` [get]
- `Boolean Visible` [get]
- `Double Volume` [get]
- `VolumnUnit VolumeUnits` [get]

Methods: 30

- `Double get_BoxMaxX()`
- `Double get_BoxMaxY()`
- `Double get_BoxMaxZ()`
- `Double get_BoxMinX()`
- `Double get_BoxMinY()`
- `Double get_BoxMinZ()`
- `Double get_CentreOfGravityX()`
- `Double get_CentreOfGravityY()`
- `Double get_CentreOfGravityZ()`
- `Double get_ColourBlue()`
- `Double get_ColourGreen()`
- `Double get_ColourRed()`
- `Double get_Density()`
- `DensityUnit get_DensityUnits()`
- `DimensionUnit get_DimensionUnits()`
- `String get_Identifier()`
- `Double get_Mass()`
- `WeightUnit get_MassUnits()`
- `String get_Material()`
- `EntityMaterialStatus get_MaterialStatus()`
- `String get_Name()`
- `Int32 get_ScanLevel()`
- `Double get_SurfaceArea()`
- `AreaUnit get_SurfaceAreaUnits()`
- `Double get_Thickness()`
- `EntityThicknessStatus get_ThicknessStatus()`
- `ThicknessUnit get_ThicknessUnits()`
- `Boolean get_Visible()`
- `Double get_Volume()`
- `VolumnUnit get_VolumeUnits()`

## Radan.Shared.Radraft.Interop.IModelPro

Properties: 0

- none

Methods: 4

- `IUnfoldResult AutoUnfold(String identifier, IUnfoldOptions unfoldOptions)`
- `IUnfoldOptions CreateUnfoldOptions()`
- `IEntityInfo FindFirstSheetMetalEntity(Boolean massPropertiesRequired)`
- `Boolean ReadModelDefault(FileType3D fileType, String file, String material, Double thickness, Double scale)`

## Radan.Shared.Radraft.Interop.INestProject

Properties: 2

- `Boolean IsEdited` [get]
- `Boolean IsOpen` [get]

Methods: 5

- `Boolean get_IsEdited()`
- `Boolean get_IsOpen()`
- `Boolean New(String projectName, String projectFolder, Boolean initializeFromCurrentlyOpenProject)`
- `Boolean Open(String nestProjectFile)`
- `Boolean Save()`

## Radan.Shared.Radraft.Interop.IPartEditor

Properties: 5

- `Boolean IsOpen` [get]
- `String Material` [get/set]
- `String Strategy` [get/set]
- `Double Thickness` [get/set]
- `ThicknessUnit ThicknessUnits` [get/set]

Methods: 18

- `Boolean AutoTool(Double& [out] errorStatus)`
- `Boolean CalculateCycleTime(Double& [out] cycleTime, String& [out] message)`
- `ICalculateCycleTimeResult CalculateCycleTime(String symbolFileFullPath, String material, Double thickness, ThicknessUnit thicknessUnits, String defaultStrategy)`
- `Void DrawRectangle(Double x, Double y, Double width, Double height)`
- `Boolean GeometryIsClosed()`
- `Boolean get_IsOpen()`
- `String get_Material()`
- `String get_Strategy()`
- `Double get_Thickness()`
- `ThicknessUnit get_ThicknessUnits()`
- `Boolean HasTooling()`
- `Boolean MaterialAndThicknessMatchAttributes(String material, Double thickness, ThicknessUnit thicknessUnits)`
- `Void Open(String filename, Boolean discardChanges, String optionsFilePath)`
- `Void RemoveTooling()`
- `Void set_Material(String value)`
- `Void set_Strategy(String value)`
- `Void set_Thickness(Double value)`
- `Void set_ThicknessUnits(ThicknessUnit value)`

## Radan.Shared.Radraft.Interop.IRadanAttribute

Properties: 0

- none

Methods: 4

- `Boolean GetCustomAttribute(Int32 attributeNumber, String& [out] value)`
- `Boolean GetRadanAttribute(RadanAttributeNumber radanAttributeNumber, String& [out] value)`
- `Boolean SetCustomAttribute(Int32 attributeNumber, String value)`
- `Boolean SetRadanAttribute(RadanAttributeNumber radanAttributeNumber, String value)`

## Radan.Shared.Radraft.Interop.IRadanMacro

Properties: 0

- none

Methods: 3

- `Void LoadMacro(String macro)`
- `Void RunMacCommand(String procedureName, Object[] arguments)`
- `Void UnloadMacro()`

## Radan.Shared.Radraft.Interop.IRadanPartAttribute

Properties: 6

- `String Material` [get/set]
- `String Name` [get/set]
- `NestOrientation Orientation` [get/set]
- `String Strategy` [get/set]
- `Double Thickness` [get/set]
- `ThicknessUnit ThicknessUnits` [get/set]

Methods: 13

- `String get_Material()`
- `String get_Name()`
- `NestOrientation get_Orientation()`
- `String get_Strategy()`
- `Double get_Thickness()`
- `ThicknessUnit get_ThicknessUnits()`
- `Void set_Material(String value)`
- `Void set_Name(String value)`
- `Void set_Orientation(NestOrientation value)`
- `Void set_Strategy(String value)`
- `Void set_Thickness(Double value)`
- `Void set_ThicknessUnits(ThicknessUnit value)`
- `Boolean SetPartEditorAttributes()`

## Radan.Shared.Radraft.Interop.IRadraftApplication

Properties: 30

- `Boolean Disposed` [get]
- `IDrawingEditor DrawingEditor` [get]
- `String FI0` [get]
- `Int32 FP0` [get]
- `String FT0` [get]
- `Boolean IsConnected` [get]
- `Boolean IsRadanInstalled` [get]
- `RadLanguage Language` [get]
- `UInt32 LineType` [get]
- `Int32 LL0` [get]
- `UInt32 LT0` [get]
- `IModelPro ModelPro` [get]
- `Double MT0` [get]
- `Int32 MTTYPE` [get]
- `Boolean NCD` [get]
- `INestProject NestProject` [get]
- `String PART_PATTERN` [get]
- `IPartEditor PartEditor` [get]
- `String PCC_PATTERN_LAYOUT` [get]
- `Int32 ProcessId` [get]
- `IRadanAttribute RadanAttribute` [get]
- `Double S0X` [get]
- `Double S0Y` [get]
- `SystemDataFiles SystemDataFiles` [get]
- `Double TE0X` [get]
- `Double TE0Y` [get]
- `String TF0` [get]
- `Double TS0X` [get]
- `Double TS0Y` [get]
- `Boolean Visible` [get/set]

Methods: 70

- `IEnumerable`1 CalculateUtilisations(String symbolFilePath, String material, Double thickness, ThicknessUnit thicknessUnit, String strategy, NestOrientation nestOrientation)`
- `Boolean ChangeMachine(String machineFileName)`
- `Boolean ChangeMachine(Int32 machineNumber)`
- `Void CloseActiveDocument(Boolean discardChanges)`
- `Boolean CloseProject()`
- `Boolean CreateThumbnail(String filename, Int32 height, Int32 width)`
- `Boolean DFix()`
- `Boolean ElfBounds(String sourcePattern, String reserved, Double& [out] left, Double& [out] bottom, Double& [out] right, Double& [out] top)`
- `Boolean ExecuteMacCode(String line)`
- `Boolean Find()`
- `Boolean FindXYIdentifier(String identifier, Double x, Double y)`
- `Boolean fla_convert_vdf_file(Boolean allowMultiBody, String vdfFilePath, String outputSymbolFilePath, IReadOnlyDictionary`2& [out] symbolFiles, String& [out] errorMessage)`
- `Boolean fla_create_zip_embed_silent(String folder, Boolean allMachines, Boolean includeProject)`
- `Boolean get_Disposed()`
- `IDrawingEditor get_DrawingEditor()`
- `String get_FI0()`
- `Int32 get_FP0()`
- `String get_FT0()`
- `Boolean get_IsConnected()`
- `Boolean get_IsRadanInstalled()`
- `RadLanguage get_Language()`
- `UInt32 get_LineType()`
- `Int32 get_LL0()`
- `UInt32 get_LT0()`
- `IModelPro get_ModelPro()`
- `Double get_MT0()`
- `Int32 get_MTTYPE()`
- `Boolean get_NCD()`
- `INestProject get_NestProject()`
- `String get_PART_PATTERN()`
- `IPartEditor get_PartEditor()`
- `String get_PCC_PATTERN_LAYOUT()`
- `Int32 get_ProcessId()`
- `IRadanAttribute get_RadanAttribute()`
- `Double get_S0X()`
- `Double get_S0Y()`
- `SystemDataFiles get_SystemDataFiles()`
- `Double get_TE0X()`
- `Double get_TE0Y()`
- `String get_TF0()`
- `Double get_TS0X()`
- `Double get_TS0Y()`
- `Boolean get_Visible()`
- `String GetDefaultStrategy(String material, Double thickness, ThicknessUnit thicknessUnit)`
- `String GetDefaultStrategyOld(String material, Double thickness, ThicknessUnit thicknessUnit)`
- `Double GetNumberInMacCode(String name)`
- `String GetStringInMacCode(String name)`
- `Boolean IsToolSym(String path)`
- `IRadanMacro LoadMacro(String macro)`
- `Boolean MtmGet(Double mtn)`
- `Void NewDrawing(Boolean discardChanges)`
- `Void NewSymbol(Boolean discardChanges)`
- `Int32 Next()`
- `Void OpenDrawing(String filePath, Boolean discardChanges, String optionsFilePath)`
- `Void OpenSymbol(String filePath, Boolean discardChanges, String optionsFilePath)`
- `Boolean PatternGeometryIsClosed(String pattern)`
- `Int32 PccGetCurrentMcId()`
- `Boolean Rewind()`
- `Int32 RfMac(String command)`
- `Int32 RunNester()`
- `Void SaveActiveDocument()`
- `Void SaveActiveDocumentAs(String filename)`
- `Void SaveCopyOfActiveDocumentAs(String filename, String optionsFilePath)`
- `Boolean Scan(String path, String filter, Int32 number)`
- `Void set_Visible(Boolean value)`
- `Boolean SetGuiState(RadGUIState radGuiState)`
- `Boolean SetNumberInMacCode(String name, Double value)`
- `Boolean SetStringInMacCode(String name, String value)`
- `Int32 Silent_exit_nc_mode()`
- `Int32 Silent_nc_mode()`

## Radan.Shared.Radraft.Interop.IRadraftApplicationFactory

Properties: 0

- none

Methods: 2

- `IRadraftApplication Create()`
- `IRadraftApplication Create(Boolean useExistingInstance)`

## Radan.Shared.Radraft.Interop.ISheetUtilisationResult

Properties: 5

- `DimensionUnit DimensionUnits` [get/set]
- `Double DimensionX` [get/set]
- `Double DimensionY` [get/set]
- `Int32 PartCount` [get/set]
- `Decimal UsableSheetUtilisation` [get/set]

Methods: 10

- `DimensionUnit get_DimensionUnits()`
- `Double get_DimensionX()`
- `Double get_DimensionY()`
- `Int32 get_PartCount()`
- `Decimal get_UsableSheetUtilisation()`
- `Void set_DimensionUnits(DimensionUnit value)`
- `Void set_DimensionX(Double value)`
- `Void set_DimensionY(Double value)`
- `Void set_PartCount(Int32 value)`
- `Void set_UsableSheetUtilisation(Decimal value)`

## Radan.Shared.Radraft.Interop.IUnfoldOptions

Properties: 15

- `Double AreaPercentFromBest` [get/set]
- `Int32 BendPath` [get/set]
- `Int32 CountFromBest` [get/set]
- `String DevelopmentPattern` [get/set]
- `String Material` [get/set]
- `Boolean Smoothing` [get/set]
- `Boolean SmoothingCircular` [get/set]
- `Double SmoothingRadius` [get/set]
- `Double SmoothingSize` [get/set]
- `Boolean SmoothingSquare` [get/set]
- `Double Thickness` [get/set]
- `ThicknessUnit ThicknessUnits` [get/set]
- `Boolean TopSurface` [get/set]
- `UnfoldAnalysisType UnfoldAnalysisType` [get/set]
- `Boolean UnfoldToPartEditor` [get/set]

Methods: 31

- `Double get_AreaPercentFromBest()`
- `Int32 get_BendPath()`
- `Int32 get_CountFromBest()`
- `String get_DevelopmentPattern()`
- `String get_Material()`
- `Boolean get_Smoothing()`
- `Boolean get_SmoothingCircular()`
- `Double get_SmoothingRadius()`
- `Double get_SmoothingSize()`
- `Boolean get_SmoothingSquare()`
- `Double get_Thickness()`
- `ThicknessUnit get_ThicknessUnits()`
- `Boolean get_TopSurface()`
- `UnfoldAnalysisType get_UnfoldAnalysisType()`
- `Boolean get_UnfoldToPartEditor()`
- `Void set_AreaPercentFromBest(Double value)`
- `Void set_BendPath(Int32 value)`
- `Void set_CountFromBest(Int32 value)`
- `Void set_DevelopmentPattern(String value)`
- `Void set_Material(String value)`
- `Void set_Smoothing(Boolean value)`
- `Void set_SmoothingCircular(Boolean value)`
- `Void set_SmoothingRadius(Double value)`
- `Void set_SmoothingSize(Double value)`
- `Void set_SmoothingSquare(Boolean value)`
- `Void set_Thickness(Double value)`
- `Void set_ThicknessUnits(ThicknessUnit value)`
- `Void set_TopSurface(Boolean value)`
- `Void set_UnfoldAnalysisType(UnfoldAnalysisType value)`
- `Void set_UnfoldToPartEditor(Boolean value)`
- `Void SetMacValues(Mac mac)`

## Radan.Shared.Radraft.Interop.IUnfoldResult

Properties: 10

- `Double DevelopedArea` [get]
- `Int32 DevelopedFacesCount` [get]
- `String DevelopmentPattern` [get]
- `DevelopmentType DevelopmentType` [get]
- `String Error` [get]
- `Boolean HasInvalidForms` [get]
- `Boolean Success` [get]
- `Double Thickness` [get]
- `ThicknessUnit ThicknessUnits` [get]
- `Int32 WarningsCount` [get]

Methods: 10

- `Double get_DevelopedArea()`
- `Int32 get_DevelopedFacesCount()`
- `String get_DevelopmentPattern()`
- `DevelopmentType get_DevelopmentType()`
- `String get_Error()`
- `Boolean get_HasInvalidForms()`
- `Boolean get_Success()`
- `Double get_Thickness()`
- `ThicknessUnit get_ThicknessUnits()`
- `Int32 get_WarningsCount()`

## Radraft.Interop.Application

Properties: 0

- none

Methods: 0

- none

## Radraft.Interop.ApplicationEvents

Properties: 0

- none

Methods: 0

- none

## Radraft.Interop.ApplicationEvents_Event

Properties: 0

- none

Methods: 0

- none

## Radraft.Interop.Document

Properties: 0

- none

Methods: 0

- none

## Radraft.Interop.IApplication

Properties: 11

- `Document ActiveDocument` [get]
- `Application Application` [get]
- `String DatPath` [get]
- `RadLanguage Language` [get]
- `Mac Mac` [get]
- `MacFiles MacFiles` [get]
- `String Name` [get]
- `Int32 ProcessID` [get]
- `String SoftwareVersion` [get]
- `SystemDataFiles SystemDataFiles` [get]
- `Boolean Visible` [get/set]

Methods: 17

- `Document get_ActiveDocument()`
- `Application get_Application()`
- `String get_DatPath()`
- `RadLanguage get_Language()`
- `Mac get_Mac()`
- `MacFiles get_MacFiles()`
- `String get_Name()`
- `Int32 get_ProcessID()`
- `String get_SoftwareVersion()`
- `SystemDataFiles get_SystemDataFiles()`
- `Boolean get_Visible()`
- `Void NewDrawing(Boolean DiscardChanges)`
- `Void NewSymbol(Boolean DiscardChanges)`
- `Void OpenDrawing(String FilePath, Boolean DiscardChanges, String OptionsFilePath)`
- `Void OpenSymbol(String FilePath, Boolean DiscardChanges, String OptionsFilePath)`
- `Boolean Quit()`
- `Void set_Visible(Boolean pVisible)`

## Radraft.Interop.IDocument

Properties: 0

- none

Methods: 4

- `Void Close(Boolean DiscardChanges)`
- `Void Save()`
- `Void SaveAs(String FilePath)`
- `Void SaveCopyAs(String FilePath, String OptionsFilePath)`

## Radraft.Interop.IMac

Properties: 115

- `Double DRU` [get]
- `String FI0` [get]
- `Int32 FP0` [get]
- `String FT0` [get]
- `Int32 LAY_BATCH` [get/set]
- `Boolean LAY_CLAMPSTRIP` [get/set]
- `Double LAY_CLAMPWIDTH` [get/set]
- `String LAY_COMP` [get/set]
- `Double LAY_COMP_AREA` [get/set]
- `String LAY_MATERIAL` [get/set]
- `Double LAY_MIN_DAT` [get/set]
- `Double LAY_MIN_NONDAT` [get/set]
- `Double LAY_MIN_UNCLAMPED` [get/set]
- `Int32 LAY_ORIENTATION` [get/set]
- `Boolean LAY_OVERPRODUCE` [get/set]
- `Int32 LAY_SHEET_SOURCE` [get/set]
- `String LAY_SHEET_UNITS` [get/set]
- `Int32 LAY_SHEETS_STANDARD` [get]
- `Double LAY_SHEETX` [get/set]
- `Double LAY_SHEETY` [get/set]
- `String LAY_STRATEGY` [get/set]
- `String LAY_THICK_UNITS` [get/set]
- `Double LAY_THICKNESS` [get/set]
- `Int32 LAY_TOTAL` [get/set]
- `Boolean LAY_TRUE_SHAPE` [get/set]
- `Int32 LL0` [get]
- `UInt32 LT0` [get]
- `Int32 MFL_MATERIAL_IMPORT_DEFAULT` [get]
- `Int32 MFL_MATERIAL_LEGACY` [get]
- `Int32 MFL_MATERIAL_SET_BY_USER` [get]
- `Int32 MFL_MATERIAL_SET_FROM_MAC` [get]
- `Int32 MFL_MATERIAL_TRANSLATED` [get]
- `Int32 MFL_MATERIAL_UNKNOWN` [get]
- `Int32 MFL_THICKNESS_CALCULATED` [get]
- `Int32 MFL_THICKNESS_CALCULATION_FAILED` [get]
- `Int32 MFL_THICKNESS_IMPORT_DEFAULT` [get]
- `Int32 MFL_THICKNESS_LEGACY` [get]
- `Int32 MFL_THICKNESS_SET_BY_USER` [get]
- `Int32 MFL_THICKNESS_SET_FROM_MAC` [get]
- `Int32 MFL_THICKNESS_TRANSLATED` [get]
- `Int32 MFL_THICKNESS_UNKNOWN` [get]
- `String MFL_U_DEV_NAME_SPEC` [get/set]
- `String MFL_U_DEV_PATTERN_RES` [get]
- `Double MFL_U_DF_AREA_RES` [get]
- `Int32 MFL_U_DF_COUNT_RES` [get]
- `String MFL_U_ERROR_RES` [get]
- `Double MFL_U_INFO_DF_AREA_SPEC` [get/set]
- `Int32 MFL_U_INFO_DF_COUNT_SPEC` [get/set]
- `Boolean MFL_U_INVALID_FORM` [get]
- `String MFL_U_MATERIAL_SPEC` [get/set]
- `Boolean MFL_U_PART_EDITOR_SPEC` [get/set]
- `Int32 MFL_U_PATH_SPEC` [get/set]
- `Boolean MFL_U_SMOOTHING` [get/set]
- `Boolean MFL_U_SMOOTHING_CIRCULAR` [get/set]
- `Double MFL_U_SMOOTHING_RADIUS` [get/set]
- `Double MFL_U_SMOOTHING_SIZE` [get/set]
- `Boolean MFL_U_SMOOTHING_SQUARE` [get/set]
- `Double MFL_U_THICKNESS_RES` [get]
- `Double MFL_U_THICKNESS_SPEC` [get/set]
- `Boolean MFL_U_TOP_SURFACE_SPEC` [get/set]
- `Int32 MFL_U_TYPE_INFO` [get]
- `Int32 MFL_U_TYPE_PATH` [get]
- `Int32 MFL_U_TYPE_RES` [get]
- `Int32 MFL_U_TYPE_SHEET` [get]
- `Int32 MFL_U_TYPE_SKIN` [get]
- `Int32 MFL_U_TYPE_SPEC` [get/set]
- `Int32 MFL_U_TYPE_THICKNESS` [get]
- `Int32 MFL_U_WARNINGS_COUNT` [get]
- `Double MT0` [get]
- `Int32 MTTYPE` [get]
- `Boolean NCD` [get]
- `Double ND_BOXMAXX1` [get]
- `Double ND_BOXMAXY1` [get]
- `Double ND_BOXMAXZ1` [get]
- `Double ND_BOXMINX1` [get]
- `Double ND_BOXMINY1` [get]
- `Double ND_BOXMINZ1` [get]
- `Double ND_COFGX1` [get]
- `Double ND_COFGY1` [get]
- `Double ND_COFGZ1` [get]
- `Double ND_COLBLUE1` [get]
- `Double ND_COLGREEN1` [get]
- `Double ND_COLRED1` [get]
- `Double ND_DENSITY1` [get]
- `String ND_IDENT1` [get]
- `Double ND_MASS1` [get]
- `String ND_MATERIAL1` [get]
- `Int32 ND_MATERIALSTATUS1` [get]
- `String ND_NAME1` [get]
- `Int32 ND_SCANLEVEL1` [get]
- `Double ND_SURFAREA1` [get]
- `Double ND_THICKNESS1` [get]
- `Int32 ND_THICKSTATUS1` [get]
- `String ND_THICKUNITS1` [get]
- `Boolean ND_VIS1` [get]
- `Double ND_VOLUME1` [get]
- `String PART_PATTERN` [get]
- `String PCC_PATTERN_LAYOUT` [get]
- `Boolean PRJ_PROJECT_CREATE_SUBFOLDER` [get/set]
- `String PRJ_PROJECT_LOCATION` [get/set]
- `String PRJ_PROJECT_NAME` [get/set]
- `Boolean PRJ_PROJECT_RESET_NEST_NUM` [get/set]
- `String PRJ_PROJECT_SAVE_NESTS_FOLDER` [get/set]
- `String PRJ_PROJECT_SAVE_REMNANTS_FOLDER` [get/set]
- `Boolean PRJ_PROJECT_USE_CURRENT` [get/set]
- `String PRJ_PROJECT_USE_REMNANTS_FOLDER` [get/set]
- `Double S0X` [get]
- `Double S0Y` [get]
- `Double TE0X` [get]
- `Double TE0Y` [get]
- `String TF0` [get]
- `Double TS0X` [get]
- `Double TS0Y` [get]
- `Double UX` [get/set]
- `Double UY` [get/set]

Methods: 211

- `Boolean att_free(Int32 handle)`
- `Boolean att_get_value(Int32 handle, Int32 number, String& [out] Value)`
- `Boolean att_set_value(Int32 handle, Int32 number, String Value)`
- `Boolean bki_get_strategy_levels(Int32& [out] numLevels, String& [out] levels)`
- `Boolean d_fix()`
- `Boolean elf_bounds(String sourcePattern, String reserved, Double& [out] left, Double& [out] bottom, Double& [out] right, Double& [out] top)`
- `Boolean elf_closed(String pattern, Int32 graphicsMode)`
- `Double elf_set_option(String option, Double Value)`
- `Boolean end_scan()`
- `Boolean Execute(String line)`
- `Boolean find()`
- `Boolean find_xy_identifier(String identifier, Double x, Double y)`
- `Boolean fla_create_zip_embed_silent(String folder, Boolean allMachines, Boolean includeProject)`
- `Boolean fla_thumbnail(String File, Int32 width, Int32 height)`
- `Int32 fmac2(String command)`
- `Double get_DRU()`
- `String get_FI0()`
- `Int32 get_FP0()`
- `String get_FT0()`
- `Int32 get_LAY_BATCH()`
- `Boolean get_LAY_CLAMPSTRIP()`
- `Double get_LAY_CLAMPWIDTH()`
- `String get_LAY_COMP()`
- `Double get_LAY_COMP_AREA()`
- `String get_LAY_MATERIAL()`
- `Double get_LAY_MIN_DAT()`
- `Double get_LAY_MIN_NONDAT()`
- `Double get_LAY_MIN_UNCLAMPED()`
- `Int32 get_LAY_ORIENTATION()`
- `Boolean get_LAY_OVERPRODUCE()`
- `Int32 get_LAY_SHEET_SOURCE()`
- `String get_LAY_SHEET_UNITS()`
- `Int32 get_LAY_SHEETS_STANDARD()`
- `Double get_LAY_SHEETX()`
- `Double get_LAY_SHEETY()`
- `String get_LAY_STRATEGY()`
- `String get_LAY_THICK_UNITS()`
- `Double get_LAY_THICKNESS()`
- `Int32 get_LAY_TOTAL()`
- `Boolean get_LAY_TRUE_SHAPE()`
- `Int32 get_LL0()`
- `UInt32 get_LT0()`
- `Int32 get_MFL_MATERIAL_IMPORT_DEFAULT()`
- `Int32 get_MFL_MATERIAL_LEGACY()`
- `Int32 get_MFL_MATERIAL_SET_BY_USER()`
- `Int32 get_MFL_MATERIAL_SET_FROM_MAC()`
- `Int32 get_MFL_MATERIAL_TRANSLATED()`
- `Int32 get_MFL_MATERIAL_UNKNOWN()`
- `Int32 get_MFL_THICKNESS_CALCULATED()`
- `Int32 get_MFL_THICKNESS_CALCULATION_FAILED()`
- `Int32 get_MFL_THICKNESS_IMPORT_DEFAULT()`
- `Int32 get_MFL_THICKNESS_LEGACY()`
- `Int32 get_MFL_THICKNESS_SET_BY_USER()`
- `Int32 get_MFL_THICKNESS_SET_FROM_MAC()`
- `Int32 get_MFL_THICKNESS_TRANSLATED()`
- `Int32 get_MFL_THICKNESS_UNKNOWN()`
- `String get_MFL_U_DEV_NAME_SPEC()`
- `String get_MFL_U_DEV_PATTERN_RES()`
- `Double get_MFL_U_DF_AREA_RES()`
- `Int32 get_MFL_U_DF_COUNT_RES()`
- `String get_MFL_U_ERROR_RES()`
- `Double get_MFL_U_INFO_DF_AREA_SPEC()`
- `Int32 get_MFL_U_INFO_DF_COUNT_SPEC()`
- `Boolean get_MFL_U_INVALID_FORM()`
- `String get_MFL_U_MATERIAL_SPEC()`
- `Boolean get_MFL_U_PART_EDITOR_SPEC()`
- `Int32 get_MFL_U_PATH_SPEC()`
- `Boolean get_MFL_U_SMOOTHING()`
- `Boolean get_MFL_U_SMOOTHING_CIRCULAR()`
- `Double get_MFL_U_SMOOTHING_RADIUS()`
- `Double get_MFL_U_SMOOTHING_SIZE()`
- `Boolean get_MFL_U_SMOOTHING_SQUARE()`
- `Double get_MFL_U_THICKNESS_RES()`
- `Double get_MFL_U_THICKNESS_SPEC()`
- `Boolean get_MFL_U_TOP_SURFACE_SPEC()`
- `Int32 get_MFL_U_TYPE_INFO()`
- `Int32 get_MFL_U_TYPE_PATH()`
- `Int32 get_MFL_U_TYPE_RES()`
- `Int32 get_MFL_U_TYPE_SHEET()`
- `Int32 get_MFL_U_TYPE_SKIN()`
- `Int32 get_MFL_U_TYPE_SPEC()`
- `Int32 get_MFL_U_TYPE_THICKNESS()`
- `Int32 get_MFL_U_WARNINGS_COUNT()`
- `Double get_MT0()`
- `Int32 get_MTTYPE()`
- `Boolean get_NCD()`
- `Double get_ND_BOXMAXX1()`
- `Double get_ND_BOXMAXY1()`
- `Double get_ND_BOXMAXZ1()`
- `Double get_ND_BOXMINX1()`
- `Double get_ND_BOXMINY1()`
- `Double get_ND_BOXMINZ1()`
- `Double get_ND_COFGX1()`
- `Double get_ND_COFGY1()`
- `Double get_ND_COFGZ1()`
- `Double get_ND_COLBLUE1()`
- `Double get_ND_COLGREEN1()`
- `Double get_ND_COLRED1()`
- `Double get_ND_DENSITY1()`
- `String get_ND_IDENT1()`
- `Double get_ND_MASS1()`
- `String get_ND_MATERIAL1()`
- `Int32 get_ND_MATERIALSTATUS1()`
- `String get_ND_NAME1()`
- `Int32 get_ND_SCANLEVEL1()`
- `Double get_ND_SURFAREA1()`
- `Double get_ND_THICKNESS1()`
- `Int32 get_ND_THICKSTATUS1()`
- `String get_ND_THICKUNITS1()`
- `Boolean get_ND_VIS1()`
- `Double get_ND_VOLUME1()`
- `String get_PART_PATTERN()`
- `String get_PCC_PATTERN_LAYOUT()`
- `Boolean get_PRJ_PROJECT_CREATE_SUBFOLDER()`
- `String get_PRJ_PROJECT_LOCATION()`
- `String get_PRJ_PROJECT_NAME()`
- `Boolean get_PRJ_PROJECT_RESET_NEST_NUM()`
- `String get_PRJ_PROJECT_SAVE_NESTS_FOLDER()`
- `String get_PRJ_PROJECT_SAVE_REMNANTS_FOLDER()`
- `Boolean get_PRJ_PROJECT_USE_CURRENT()`
- `String get_PRJ_PROJECT_USE_REMNANTS_FOLDER()`
- `Double get_S0X()`
- `Double get_S0Y()`
- `Double get_TE0X()`
- `Double get_TE0Y()`
- `String get_TF0()`
- `Double get_TS0X()`
- `Double get_TS0Y()`
- `Double get_UX()`
- `Double get_UY()`
- `Double GetNumber(String Name)`
- `String GetString(String Name)`
- `Boolean isa_tool_sym(String Path)`
- `Int32 lay_calculate_utilisations(Boolean useSystemDataClearances, Boolean calculateCompSize)`
- `Boolean lay_clear_properties()`
- `Boolean lay_get_utilisation(Int32 index)`
- `Int32 lay_run_nest(Int32 reserved)`
- `Int32 mac2(String command)`
- `Boolean mfl_auto_unfold(String ident)`
- `Double mfl_calculate_thickness(String ident)`
- `String mfl_info_scan_next()`
- `Boolean mfl_info_scan_start()`
- `Boolean mfl_object_info(String ident, Boolean massPropertiesRequired)`
- `Boolean mfl_read_model(String fileformat, Boolean heal, Boolean regularise, Boolean reverse, Boolean combine, Boolean allowComplexGeom, Double scale, Double Thickness, String Material, String Filename)`
- `Boolean mfl_read_model_default(String fileformat, String Filename, String Material, Double Thickness, Double scale)`
- `Boolean mtm_get(Double mtn)`
- `Int32 next()`
- `Int32 pcc_get_current_mc_id()`
- `Int32 ped_attrs_handle()`
- `Boolean ped_set_attrs2(String Name, String Material, String Strategy, Double Thickness, Int32 units, Int32 orientation)`
- `Boolean pfl_auto_tool(String sourcePattern, String destinationPattern, Double reserved, Double& [out] errorStatus)`
- `Boolean pfl_get_default_mdb_strategy(Double Thickness, String ThicknessUnits, String Material, String& [out] Strategy)`
- `Boolean pfl_get_run_time(Double reserved1, String& [out] errorMessage, Double& [out] runTime, Double& [out] reserved2)`
- `Boolean prj_clear_part_data()`
- `Boolean prj_close()`
- `Boolean prj_is_edited()`
- `Boolean prj_is_open()`
- `Boolean prj_new_project()`
- `Boolean prj_open(String File)`
- `Boolean prj_save()`
- `Boolean rewind()`
- `Int32 rfmac(String command)`
- `Boolean scan(String Path, String filter, Int32 number)`
- `Void set_LAY_BATCH(Int32 __MIDL__IMac0832)`
- `Void set_LAY_CLAMPSTRIP(Boolean __MIDL__IMac0812)`
- `Void set_LAY_CLAMPWIDTH(Double __MIDL__IMac0814)`
- `Void set_LAY_COMP(String __MIDL__IMac0786)`
- `Void set_LAY_COMP_AREA(Double __MIDL__IMac0794)`
- `Void set_LAY_MATERIAL(String __MIDL__IMac0796)`
- `Void set_LAY_MIN_DAT(Double __MIDL__IMac0822)`
- `Void set_LAY_MIN_NONDAT(Double __MIDL__IMac0824)`
- `Void set_LAY_MIN_UNCLAMPED(Double __MIDL__IMac0816)`
- `Void set_LAY_ORIENTATION(Int32 __MIDL__IMac0788)`
- `Void set_LAY_OVERPRODUCE(Boolean __MIDL__IMac0834)`
- `Void set_LAY_SHEET_SOURCE(Int32 __MIDL__IMac0804)`
- `Void set_LAY_SHEET_UNITS(String __MIDL__IMac0810)`
- `Void set_LAY_SHEETX(Double __MIDL__IMac0806)`
- `Void set_LAY_SHEETY(Double __MIDL__IMac0808)`
- `Void set_LAY_STRATEGY(String __MIDL__IMac0802)`
- `Void set_LAY_THICK_UNITS(String __MIDL__IMac0800)`
- `Void set_LAY_THICKNESS(Double __MIDL__IMac0798)`
- `Void set_LAY_TOTAL(Int32 __MIDL__IMac0842)`
- `Void set_LAY_TRUE_SHAPE(Boolean __MIDL__IMac0836)`
- `Void set_MFL_U_DEV_NAME_SPEC(String __MIDL__IMac0611)`
- `Void set_MFL_U_INFO_DF_AREA_SPEC(Double __MIDL__IMac0607)`
- `Void set_MFL_U_INFO_DF_COUNT_SPEC(Int32 __MIDL__IMac0605)`
- `Void set_MFL_U_MATERIAL_SPEC(String __MIDL__IMac0609)`
- `Void set_MFL_U_PART_EDITOR_SPEC(Boolean __MIDL__IMac0857)`
- `Void set_MFL_U_PATH_SPEC(Int32 __MIDL__IMac0603)`
- `Void set_MFL_U_SMOOTHING(Boolean __MIDL__IMac0613)`
- `Void set_MFL_U_SMOOTHING_CIRCULAR(Boolean __MIDL__IMac0615)`
- `Void set_MFL_U_SMOOTHING_RADIUS(Double __MIDL__IMac0619)`
- `Void set_MFL_U_SMOOTHING_SIZE(Double __MIDL__IMac0621)`
- `Void set_MFL_U_SMOOTHING_SQUARE(Boolean __MIDL__IMac0617)`
- `Void set_MFL_U_THICKNESS_SPEC(Double __MIDL__IMac0599)`
- `Void set_MFL_U_TOP_SURFACE_SPEC(Boolean __MIDL__IMac0601)`
- `Void set_MFL_U_TYPE_SPEC(Int32 __MIDL__IMac0597)`
- `Void set_PRJ_PROJECT_CREATE_SUBFOLDER(Boolean __MIDL__IMac0647)`
- `Void set_PRJ_PROJECT_LOCATION(String __MIDL__IMac0645)`
- `Void set_PRJ_PROJECT_NAME(String __MIDL__IMac0639)`
- `Void set_PRJ_PROJECT_RESET_NEST_NUM(Boolean __MIDL__IMac0643)`
- `Void set_PRJ_PROJECT_SAVE_NESTS_FOLDER(String __MIDL__IMac0649)`
- `Void set_PRJ_PROJECT_SAVE_REMNANTS_FOLDER(String __MIDL__IMac0651)`
- `Void set_PRJ_PROJECT_USE_CURRENT(Boolean __MIDL__IMac0641)`
- `Void set_PRJ_PROJECT_USE_REMNANTS_FOLDER(String __MIDL__IMac0653)`
- `Void set_UX(Double __MIDL__IMac0325)`
- `Void set_UY(Double __MIDL__IMac0327)`
- `Boolean SetNumber(String Name, Double Value)`
- `Boolean SetString(String Name, String Value)`
- `Int32 silent_exit_nc_mode()`
- `Int32 silent_nc_mode()`

## Radraft.Interop.IMacArgument

Properties: 0

- none

Methods: 0

- none

## Radraft.Interop.IMacArguments

Properties: 0

- none

Methods: 3

- `MacArgument Append(Object ArgumentValue)`
- `Boolean Clear()`
- `MacArgument Item(Int32 ItemIndex)`

## Radraft.Interop.IMacCommand

Properties: 2

- `MacArguments MacArguments` [get]
- `String ProcedureName` [get/set]

Methods: 4

- `Boolean Execute()`
- `MacArguments get_MacArguments()`
- `String get_ProcedureName()`
- `Void set_ProcedureName(String pName)`

## Radraft.Interop.IMacCommands

Properties: 0

- none

Methods: 2

- `MacCommand Add()`
- `MacCommand Item(Int32 ItemIndex)`

## Radraft.Interop.IMacFile

Properties: 1

- `MacCommands MacCommands` [get]

Methods: 3

- `MacCommands get_MacCommands()`
- `Boolean Load(String File)`
- `Boolean Unload()`

## Radraft.Interop.IMacFiles

Properties: 0

- none

Methods: 2

- `MacFile Add()`
- `MacFile Item(Int32 ItemIndex)`

## Radraft.Interop.ISystemDataFile

Properties: 0

- none

Methods: 2

- `Void Close()`
- `SystemDataItem Item(String Key, Object DefaultValue)`

## Radraft.Interop.ISystemDataFiles

Properties: 0

- none

Methods: 2

- `SystemDataFile Item(Int32 ItemIndex)`
- `SystemDataFile Open(String Filename, RadDataFileType DataFileType)`

## Radraft.Interop.ISystemDataItem

Properties: 1

- `String Value` [get/set]

Methods: 2

- `String get_Value()`
- `Void set_Value(String pVal)`

## Radraft.Interop.Mac

Properties: 0

- none

Methods: 0

- none

## Radraft.Interop.MacArgument

Properties: 0

- none

Methods: 0

- none

## Radraft.Interop.MacArguments

Properties: 0

- none

Methods: 0

- none

## Radraft.Interop.MacCommand

Properties: 0

- none

Methods: 0

- none

## Radraft.Interop.MacCommands

Properties: 0

- none

Methods: 0

- none

## Radraft.Interop.MacFile

Properties: 0

- none

Methods: 0

- none

## Radraft.Interop.MacFiles

Properties: 0

- none

Methods: 0

- none

## Radraft.Interop.SystemDataFile

Properties: 0

- none

Methods: 0

- none

## Radraft.Interop.SystemDataFiles

Properties: 0

- none

Methods: 0

- none

## Radraft.Interop.SystemDataItem

Properties: 0

- none

Methods: 0

- none


