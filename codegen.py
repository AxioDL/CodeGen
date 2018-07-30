# C++ code generation using clang
import clang.cindex
import glob
import mako.template
import os
import sys

# Folder containing the script file
ScriptDirectory = os.path.dirname(__file__)

# [debug] Path to store auto-generated codegen source files
ExportPath = "build\\codegen"

# [debug] Path to store the final output cpp file
OutputCppSource = "%s\\auto_codegen.cpp" % ExportPath

# [debug] Path to find the source files
SourceRoot = "."

# [debug] Whether to parse parameters from the commandline
ParseCmdLine = True

# [debug] Whether to parse out source files and include paths from the command line
InputViaCommandLine = True

# Whether to always do a full regen
ForceFullRegen = False

def GetCursorFullyQualifiedName(Cursor):
	""" Return the fully qualified name of the object represented by Cursor, including any parent scopes """
	OutName = Cursor.spelling
	Cursor = Cursor.semantic_parent
		
	# not 100% sure this is correct?
	while Cursor.kind != clang.cindex.CursorKind.TRANSLATION_UNIT:
		OutName = "%s::%s" % (Cursor.spelling, OutName)
		Cursor = Cursor.semantic_parent
			
	return OutName
	
def GetCursorAnnotations(Cursor):
	""" Return all annotation strings assigned to this cursor """
	return [Child.displayname for Child in Cursor.get_children() if Child.kind is clang.cindex.CursorKind.ANNOTATE_ATTR]
	
def DebugPrintCursorRecursive(Cursor, SourceFile, Depth=0):
	Padding = ""
	for i in range(0, Depth):
		Padding += "  "
		
	print("%s%s (%s)" % (Padding, Cursor.displayname, Cursor.kind))
	
	for c in Cursor.get_children():
		if SourceFile in c.location.file.name:
			DebugPrintCursorRecursive(c, SourceFile, Depth+1)

class CxxCompileEnvironment:
	""" Compilation environment used to configure clang """
	def __init__(self, InIncludePaths):
		self.CompilerArgs = ['-x', 'c++', '-std=c++17', '-DIS_CODEGEN_SCRIPT=1']
		self.IncludePaths = InIncludePaths
	
	def GetClangArgs(self):
		return self.CompilerArgs + ["-I" + Path for Path in self.IncludePaths]
	
class CxxEnumConstant:
	""" A C++ enum constant """
	def __init__(self, Cursor):
		self.Cursor = Cursor
		self.Name = Cursor.spelling
		self.FullName = GetCursorFullyQualifiedName(Cursor)
		self.Value = Cursor.enum_value
		
		# Remove 'e' prefix from the name
		if len(self.Name) >= 2 and self.Name[0] is 'e' and self.Name[1].isupper():
			self.Name = self.Name[1:]

class CxxEnum:
	""" A C++ enum type """
	def __init__(self, Cursor):
		self.Cursor = Cursor
		self.Name = Cursor.spelling
		self.FullName = GetCursorFullyQualifiedName(Cursor)
		self.Constants = []
		self.InvalidValue = -1
		
		for Child in Cursor.get_children():
			if Child.kind is clang.cindex.CursorKind.ENUM_CONSTANT_DECL:
				Constant = CxxEnumConstant(Child)
				self.Constants.append(Constant)
				
				if "invalid" in Constant.Name.lower():
					self.InvalidValue = Constant.Value
	
	def DebugPrint(self):
		print("Enum: %s (%s)" % (GetCursorFullyQualifiedName(self.Cursor), self.Cursor.location.file))
		
		for Const in self.Constants:
			print("- %s = %d" % (Const.Name, Const.Value))
		
		print("")

class ScopedDeclare:
	""" Recursive class that represents a scoped forward declare in the generated source code """
	def __init__(self, TypeName, Name):
		self.TypeName = TypeName
		self.Name = Name
		self.Children = []
	
	def AddChild(self, TypeName, Name):
		for Child in self.Children:
			if Child.TypeName == TypeName and Child.Name == Name:
				return Child
		
		NewDeclare = ScopedDeclare(TypeName, Name)
		self.Children.append(NewDeclare)
		return self.Children[-1]
		
	def GenerateText(self, Indentation):
		OutText = ""
		
		if self.Name:
			IndentText = '\t' * Indentation
			LineEnd = " {" if self.Children else ";"
			OutText = "%s%s %s%s\n" % (IndentText, self.TypeName, self.Name, LineEnd)
		
		for Child in self.Children:
			OutText += Child.GenerateText(Indentation + 1)
		
		if self.Children:
			OutText += '\t' * Indentation
			OutText += '}'
			
			if self.TypeName is "struct":
				OutText += ';'
			
			if Indentation > 0:
				OutText += '\n'
		
		return OutText
		
	def DebugPrint(self):
		print( self.GenerateText(0) )
		
class SourceFile:
	""" A C++ source code file """
	def __init__(self, FilePath):
		self.FilePath = FilePath
		self.Enums = []
		self.RootDeclare = ScopedDeclare("", "")
		
	def GetCodegenFile(self):
		""" Returns the path to store the auto-generated code for this source file """
		if os.path.isabs(self.FilePath):
			RelativePath = self.FilePath[3:]
			return "%s\\%s.codegen.inl" % (ExportPath, RelativePath)
		else:
			return "%s\\%s.codegen.inl" % (ExportPath, self.FilePath)
	
	def LastModifiedTime(self):
		""" Returns the last modified time for this source file """
		return os.path.getmtime( self.FilePath )
		
	def Analyze(self, ClangIndex, CompileEnvironment):
		""" Analyzes the AST for any components that need generated code """
		TranslationUnit = ClangIndex.parse(self.FilePath, CompileEnvironment.GetClangArgs())
		self.CursorRecurse(TranslationUnit.cursor, 0)
		
		if self.Enums:
			# Generate code
			MakoTemplateFile = open("template.mako", "r")
			MakoTemplateText = MakoTemplateFile.read()
			MakoTemplateFile.close()
			
			MakoTemplate = mako.template.Template(MakoTemplateText)
			GeneratedCode = MakoTemplate.render(Enums=self.Enums, IncludeFile=self.FilePath, ForwardDeclares=self.RootDeclare.Children)
			
			OutPath = self.GetCodegenFile()
			OutDir = os.path.dirname(OutPath)
			os.makedirs(OutDir, exist_ok=True)
			
			OutCodegenFile = open(OutPath, "w")
			OutCodegenFile.write(GeneratedCode)
			OutCodegenFile.close()
		
	def CursorRecurse(self, Cursor, Depth):
		""" Recursive function that performs the actual analysis work of the AST """
		for Child in Cursor.get_children():
			# skip if this cursor isn't from the real source file
			# if this check passes it means the cursor is from an include file, we don't care about that
			if not Child.location.file or not Child.location.file.name.endswith(self.FilePath):
				continue
				
			# check for enum
			if Child.kind is clang.cindex.CursorKind.ENUM_DECL:
				NewEnum = CxxEnum(Child)
				self.Enums.append(NewEnum)
				
				# Register any needed nested forward declares
				Parent = Cursor
				DeclarationCursors = []
				
				while Parent is not None:
					if Parent.kind is clang.cindex.CursorKind.CLASS_DECL or Parent.kind is clang.cindex.CursorKind.STRUCT_DECL:
						DeclarationCursors.append(Parent)

					elif Parent.kind is clang.cindex.CursorKind.NAMESPACE:
						DeclarationCursors.append(Parent)

					elif Parent.kind is clang.cindex.CursorKind.TRANSLATION_UNIT:
						break
					
					Parent = Parent.semantic_parent
					
				if DeclarationCursors:
					Declaration = self.RootDeclare
					
					for i in range(len(DeclarationCursors)-1, -1, -1):
						Decl = DeclarationCursors[i]
						TypeName = "namespace" if Decl.kind is clang.cindex.CursorKind.NAMESPACE else "struct"
						Declaration = Declaration.AddChild(TypeName, Decl.spelling)
					
					Declaration.AddChild("enum", NewEnum.Name)
					
			# currently we're only testing enums - recurse for non-enum types to look for more enums
			else:
				self.CursorRecurse(Child, Depth + 1)

def RunCodegen():
	# Source files to parse
	SourceFiles = []
	IncludePaths = []

	if ParseCmdLine:
		global InputViaCommandLine
		
		for i in range(0, len(sys.argv)):
			arg = sys.argv[i]
		
			if InputViaCommandLine is True and arg == "-sourcefiles" or arg == "-include":
				i += 1
			
				while i < len(sys.argv) and sys.argv[i][0] != '-':
					File = sys.argv[i]
				
					if arg == "-sourcefiles":
						# this isn't the best way to handle this since the output file is provided via commandline arg
						if "auto_codegen" not in File:
							SourceFiles.append(File)
					else:
						IncludePaths.append(File)
				
					i += 1
				
				i -= 1
		
			# The only time we don't use commandline input is for debugging
			if arg == "-cmdinput":
				InputViaCommandLine = True
			
			if arg == "-full":
				global ForceFullRegen
				ForceFullRegen = True
			
			if arg == "-o":
				i += 1
				OutputCppSource = sys.argv[i]
			
			if arg == "-pwd":
				i += 1
				WorkingDirectory = sys.argv[i]
				os.chdir(WorkingDirectory)
				
	if not InputViaCommandLine:
		SourceFiles  = glob.glob("%s\\**\\*.cpp" % SourceRoot, recursive=True)
		SourceFiles += glob.glob("%s\\**\\*.hpp" % SourceRoot, recursive=True)
		SourceFiles += glob.glob("%s\\**\\*.h"   % SourceRoot, recursive=True)
		OutputCppSource += OutputCppSource
	
	# Clang index
	#@todo - this definitely isn't portable??? how should I be setting this???
	clang.cindex.Config.set_library_file('C:\\Program Files\\LLVM\\bin\\libclang.dll')
	ClangIndex = clang.cindex.Index.create()

	# C++ environment
	CompileEnvironment = CxxCompileEnvironment(IncludePaths)

	# Process all source files
	LastRegenTime = os.path.getmtime(OutputCppSource) if os.path.isfile(OutputCppSource) else 0
	OutFiles = []

	for FilePath in SourceFiles:
		NewFile = SourceFile(FilePath)
		NewFileOut = NewFile.GetCodegenFile()
		
		# Only run codegen on this file if it has been modified since last time
		if ForceFullRegen or NewFile.LastModifiedTime() > LastRegenTime:
			NewFile.Analyze(ClangIndex, CompileEnvironment)
		
			if NewFile.Enums:
				# Register this as a file that needs to be included in the output source
				OutFiles.append(NewFileOut)
			else:
				# Delete codegen file if it exists
				if os.path.isfile(NewFileOut):
					os.remove(NewFileOut)
		
		# If the file hasn't been modified, we still want to make sure it gets included in the output source
		elif os.path.isfile(NewFileOut):
			OutFiles.append(NewFileOut)

	# Create final output cpp
	OutDir = os.path.dirname(OutputCppSource)
	os.makedirs(OutDir, exist_ok=True)

	OutFile = open(OutputCppSource, "w")
	[OutFile.write("#include \"%s\"\n" % os.path.normpath(CodegenFile)) for CodegenFile in OutFiles]
	OutFile.close()

RunCodegen()