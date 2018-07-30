#ifndef CODEGEN_ENUMREFLECTION_H
#define CODEGEN_ENUMREFLECTION_H

#include <cstring>
#include <type_traits>
#include <unordered_map>

typedef std::unordered_map<int, const char*> CEnumNameMap;

/** Provides runtime information about enum types */
template<typename T, typename = typename std::enable_if< std::is_enum<T>::value >::type>
class TEnumReflection
{
	/** Private constructor - no instantiation */
	TEnumReflection() {}
	
	/** Map that provides mapping between enum constants and their names */
	static const CEnumNameMap skNameMap;
	
public:
	/** Returns the name of the given enum value */
	inline static const char* ConvertValueToString(T InValue)
	{
		auto FindIter = skNameMap.find(InValue);
		
		if (FindIter != skNameMap.end())
		{
			return FindIter->second;
		}
		else
		{
			return "Invalid";
		}
	}
	
	/** Returns the enum value corresponding to the given name */
	static T ConvertStringToValue(const char* InValue)
	{
		//@todo this is slow, and would also prefer the failure case to return a type-dependent default "invalid" value
		for (auto Iter = skNameMap.begin(); Iter != NameMap.end(); Iter++)
		{
			if (strcmp(Iter->second, InValue) == 0)
			{
				return Iter->first;
			}
		}
		
		return (T) -1;
	}
};

#endif