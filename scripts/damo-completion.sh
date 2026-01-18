# SPDX-License-Identifier: GPL-2.0
# bash completion support for damo

_damo_complete()
{
	local cur prev words cword
	_init_completion || return

	if [ "$cword" -lt 1 ]
	then
		return 1
	fi

	_damo_complete_debug="false"
	if [ "${_damo_complete_debug}" = "true" ]
	then
		echo "cur '$cur'" >> .damo_completion_log
		echo "prev '$prev'" >> .damo_completion_log
		echo "words '${words[@]}'" >> .damo_completion_log
		echo "cword '$cword'" >> .damo_completion_log
		echo >> .damo_completion_log
	fi

	# support only first command for now
	if [ "$cword" -ne 1 ]
	then
		return 1
	fi

	candidates="start stop tune record report help version"

	COMPREPLY=($(compgen -W "${candidates}" -- "$cur"))
	return 0
}

complete -F _damo_complete damo
