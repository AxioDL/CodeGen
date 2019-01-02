% if Enums:
#include <codegen/EnumReflection.h>
% endif

% for Decl in ForwardDeclares:
${Decl.GenerateText(0)}
% endfor

% for Enum in Enums:
template<>
const CEnumNameMap TEnumReflection<${Enum.FullName}>::skNameMap = {
<% ValueSet = set() %> \
	% for Constant in Enum.Constants:
	% if Constant.Value not in ValueSet:
	{ ${Constant.Value}, "${Constant.Name}" },
<% ValueSet.add(Constant.Value) %> \
	% endif
	% endfor
};
template<>
const int TEnumReflection<${Enum.FullName}>::skErrorValue = ${Enum.ErrorValue};

% endfor
