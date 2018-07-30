#include "codegen/EnumReflection.h"

% for Decl in ForwardDeclares:
${Decl.GenerateText(0)}
% endfor

% for Enum in Enums:
const CEnumNameMap TEnumMapper<enum ${Enum.FullName}>::skStringMap = {
	% for Constant in Enum.Constants:
	{ ${Constant.Value}, "${Constant.Name}" },
	% endfor
};

% endfor
