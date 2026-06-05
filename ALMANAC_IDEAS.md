# Idee Template ALMANAC

response(in, out): se leggo in prima o poi dovrò rispondere out

reactive_response(in, out, n): se leggo in dovrò rispondere out entro gli n prossimi step. (default: 0 quindi nello stesso step)

inhibition(in, out): se leggo in non potro mai rispondere out.

reactive_inibition(in, out, n): se leggo in non potro rispondere out per n prossimi step: (default: 0 quindi nello stesso step)

reactive_persistence_response(in_start, in_end, out): se leggo in_start dovrò rispondere out fin quando non leggerò in_end

reactive_persistence_inhibition(in_start, in_end, out): se leggo in_start non potrò rispondere out fin quando non leggerò out (oppure finirà la traccia)

proactive_chain(out_1, out_2, ...): vi è una precedenza tra le risposte, non posso rispondere out_2 se non ho risposto out_1 e così via 

proactive_exclusion(out_1, out_2, ...): se rispondo un out_i non potrò più rispondere out_j con j != i

proactive_step_exclusion(out_1, out_2, ...): in uno step posso rispondere al massimo una delle risposte out_1, out_2, ...

proactive_alternate(out_a, out_b): dopo aver risposto out_a, dovrò rispondere out_b prima di poter rispondere out_a di nuovo, stesso vale per out_b.

