% if Enums:
#include <codegen/EnumReflection.h>
% endif
#include "${IncludeFile}"

#pragma warning( push )
#pragma warning( disable : 4146 ) // Suppress C4146: unary minus operator applied to unsigned type, result still unsigned
#pragma warning( disable : 4244 ) // 'conversion' conversion from 'type1' to 'type2', possible loss of data

## % for Decl in ForwardDeclares:
## ${Decl.GenerateText(0)}
## % endfor

% for Enum in Enums:
template <>
const CEnumNameMap TEnumReflection<${Enum.FullName}>::skNameMap = {
<% ValueSet = set() %> \
	% for Constant in Enum.Constants:
	% if Constant.Value not in ValueSet:
	{ ${Constant.Value}, "${Constant.Name}" },
<% ValueSet.add(Constant.Value) %> \
	% endif
	% endfor
};

template <>
const int TEnumReflection<${Enum.FullName}>::skErrorValue = ${Enum.ErrorValue};

% endfor

#pragma warning( pop )
