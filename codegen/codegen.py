# C++ code generation using clang
import clang.cindex
import cProfile
import mako.template
import os

from typing import List, Iterable, Optional

# Directory that the codegen script file is stored in
TemplateDir = os.path.normpath(os.path.join(os.path.dirname(__file__), 'data'))

# [debug] Whether to enable profiling
EnableProfiling = False

# [debug] Whether to print the AST for each processed source file
PrintAST = False

# [debug] Path to store auto-generated codegen source files
ExportPath = "build/codegen"

# [debug] Path to store the final output cpp file
OutputCppSource = "%s/auto_codegen.cpp" % ExportPath

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
		if c.location.file and SourceFile in c.location.file.name:
			DebugPrintCursorRecursive(c, SourceFile, Depth+1)

class CxxCompileEnvironment:
	""" Compilation environment used to configure clang """
	def __init__(self, InIncludePaths):
		# Disabling standard includes massively speeds up parsing time.
		# We still need custom includes for things like the FOURCC macro, but standard includes are generally not needed.
		self.CompilerArgs = ['-x', 'c++', '-std=c++17', '-nobuiltininc', '-nostdinc', '-nostdinc++', '-DIS_CODEGEN_SCRIPT=1']
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
		
		# Remove 'e' or 'k' prefix from the name
		if len(self.Name) >= 2 and (self.Name[0] is 'e' or self.Name[0] is 'k') and not self.Name[1].islower():
			self.Name = self.Name[1:]

class CxxEnum:
	""" A C++ enum type """
	def __init__(self, Cursor):
		self.Cursor = Cursor
		self.Name = Cursor.spelling
		self.FullName = GetCursorFullyQualifiedName(Cursor)
		self.Constants = []
		self.ErrorValue = -1
		
		for Child in Cursor.get_children():
			if Child.kind is clang.cindex.CursorKind.ENUM_CONSTANT_DECL:
				Constant = CxxEnumConstant(Child)
				self.Constants.append(Constant)
				
				LowercaseName = Constant.Name.lower()
				if Constant.Value == -1 or "invalid" in LowercaseName or "unknown" in LowercaseName:
					self.ErrorValue = Constant.Value
	
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
		
	def GetCodegenFile(self, SourceRoot: str, OutputRoot: str):
		""" Returns the path to store the auto-generated code for this source file """
		abspath = os.path.abspath(self.FilePath)
		relpath = os.path.relpath(abspath, SourceRoot)
		reldir, filename = os.path.split(relpath)
		filename_no_ext, ext = os.path.splitext(filename)
		if len(ext):
			ext = ext[1:]
		return os.path.join(OutputRoot, reldir, filename_no_ext + '_' + ext + '_codegen.cpp')
	
	def LastModifiedTime(self):
		""" Returns the last modified time for this source file """
		return os.path.getmtime(self.FilePath)
	
	def Analyze(self, ClangIndex, CompileEnvironment):
		""" Analyzes the AST for any components that need generated code """
		TranslationUnit = ClangIndex.parse(self.FilePath, CompileEnvironment.GetClangArgs())
		self.UsedSymbols = set()
		self.CursorRecurse(TranslationUnit.cursor, 0)
		
		if PrintAST:
			DebugPrintCursorRecursive(TranslationUnit.cursor, self.FilePath)
			print("")

	def Generate(self, OutputPath: str):
		if self.Enums:
			with open("%s/template.mako" % TemplateDir, "r") as MakoTemplateFile:
				MakoTemplateText = MakoTemplateFile.read()

			MakoTemplate = mako.template.Template(MakoTemplateText)
			GeneratedCode = MakoTemplate.render(Enums=self.Enums, IncludeFile=self.FilePath,
												ForwardDeclares=self.RootDeclare.Children)

			OutDir = os.path.dirname(OutputPath)
			os.makedirs(OutDir, exist_ok=True)

			with open(OutputPath, "w") as file:
				file.write(GeneratedCode)
		
	def CursorRecurse(self, Cursor, Depth):
		""" Recursive function that performs the actual analysis work of the AST """
		for Child in Cursor.get_children():
			# skip if this cursor isn't from the real source file
			# if this check passes it means the cursor is from an include file, we don't care about that
			if not Child.location.file or not Child.location.file.name.endswith(self.FilePath):
				continue
				
			# check for enum; anonymous enums are not supported
			if Child.kind is clang.cindex.CursorKind.ENUM_DECL and Child.spelling:
				# avoid the same enum being registered twice. This happens if you declare an enum and a variable of that enum simultaneously
				QualifiedName = GetCursorFullyQualifiedName(Child)
				
				if QualifiedName in self.UsedSymbols:
					continue
				else:
					self.UsedSymbols.add(QualifiedName)
					
				NewEnum = CxxEnum(Child)
				self.Enums.append(NewEnum)
				
				# Register any needed forward declares
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


def RunCodegen(file_path: str, include_paths: Iterable[str], lib_clang_path: str, source_root: str, output_root: str):
	file = GetAnalyzedSourceFile(file_path, include_paths, lib_clang_path)
	output_path = file.GetCodegenFile(source_root, output_root)
	file.Generate(output_path)


# if EnableProfiling:
# 	cProfile.run('RunCodegen()')
# else:
# 	RunCodegen()


def GetAnalyzedSourceFile(FilePath: str, IncludePaths: Iterable[str], LibClangPath: str) -> SourceFile:
	# Clang index
	clang.cindex.Config.set_library_file(LibClangPath)
	ClangIndex = clang.cindex.Index.create()

	# C++ environment
	CompileEnvironment = CxxCompileEnvironment(IncludePaths)

	NewFile = SourceFile(FilePath)
	NewFile.Analyze(ClangIndex, CompileEnvironment)
	return NewFile


def get_output_files(
		source_file: str,
		include_paths: Iterable[str],
		lib_clang_path: str,
		source_root: str,
		output_root: str,
		cache_path: Optional[str]
) -> List[str]:

	file = GetAnalyzedSourceFile(source_file, include_paths, lib_clang_path)

	if not file.Enums:
		output_files = []
	else:
		output_files = [file.GetCodegenFile(source_root, output_root)]

	if cache_path:
		cache_output_files(cache_path, source_root, source_file, output_files)

	return output_files


def cache_output_files(cache_path: str, source_root: str, file_path: str, output_files: List[str]) -> None:
	cache_file_path = get_output_files_cache_filename(cache_path, source_root, file_path)
	cache_file_dir = os.path.dirname(cache_file_path)
	os.makedirs(cache_file_dir, exist_ok=True)
	with open(cache_file_path, 'w') as f:
		f.write(';'.join(output_files))


def get_output_files_cache_filename(cache_path: str, source_root: str, file_path: str) -> str:
	abspath = os.path.abspath(file_path)
	relpath = os.path.relpath(abspath, source_root)
	return os.path.normpath(os.path.join(cache_path, relpath) + '.outputs')
